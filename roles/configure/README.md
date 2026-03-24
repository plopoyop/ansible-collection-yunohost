# configure

 Configure a YunoHost server: postinstall, global settings, domains,
users, firewall, applications, and permissions.
Requires `become: true` — all operations need root access.

## Table of contents

- [Requirements](#requirements)
- [Default Variables](#default-variables)
  - [yunohost_admin_fullname](#yunohost_admin_fullname)
  - [yunohost_admin_password](#yunohost_admin_password)
  - [yunohost_admin_username](#yunohost_admin_username)
  - [yunohost_apps](#yunohost_apps)
  - [yunohost_domains](#yunohost_domains)
  - [yunohost_firewall_ports](#yunohost_firewall_ports)
  - [yunohost_force_diskspace](#yunohost_force_diskspace)
  - [yunohost_ignore_dyndns](#yunohost_ignore_dyndns)
  - [yunohost_main_domain](#yunohost_main_domain)
  - [yunohost_overwrite_root_password](#yunohost_overwrite_root_password)
  - [yunohost_permissions](#yunohost_permissions)
  - [yunohost_settings_email](#yunohost_settings_email)
  - [yunohost_settings_misc](#yunohost_settings_misc)
  - [yunohost_settings_security](#yunohost_settings_security)
  - [yunohost_users](#yunohost_users)
- [Dependencies](#dependencies)
- [License](#license)
- [Author](#author)

---

## Requirements

- Minimum Ansible version: `2.15`

## Default Variables

### yunohost_admin_fullname

Full name of the primary admin user

**_Type:_** string<br />

#### Default value

```YAML
yunohost_admin_fullname: ''
```

### yunohost_admin_password

Password for the primary admin user

**_Type:_** string<br />

#### Default value

```YAML
yunohost_admin_password: ''
```

### yunohost_admin_username

Primary admin username created during postinstall

**_Type:_** string<br />

#### Default value

```YAML
yunohost_admin_username: ''
```

### yunohost_apps

List of applications to manage. Each entry: name (required),
state (present/absent/latest), domain (str), path (str), label (str),
args (dict), force (bool), purge (bool), no_safety_backup (bool)

**_Type:_** list<br />

#### Default value

```YAML
yunohost_apps: []
```

#### Example usage

```YAML
  yunohost_apps:
    - name: nextcloud
      domain: cloud.example.com
      path: /
      args:
        admin: admin
```

### yunohost_domains

List of domains to manage. Each entry: name (required), state (present/absent),
main (bool), remove_apps (bool), force (bool), install_letsencrypt_cert (bool),
ignore_dyndns (bool), settings (dict), ignore_unavailable (bool, default true)

**_Type:_** list<br />

#### Default value

```YAML
yunohost_domains: []
```

#### Example usage

```YAML
  yunohost_domains:
    - name: example.com
      main: true
      settings:
        portal_title: "My Server"
    - name: old.example.com
      state: absent
```

### yunohost_firewall_ports

List of firewall port rules. Each entry: port (required),
state (open/closed), protocol (tcp/udp/both), comment (str), upnp (bool)

**_Type:_** list<br />

#### Default value

```YAML
yunohost_firewall_ports: []
```

#### Example usage

```YAML
  yunohost_firewall_ports:
    - { port: 80, comment: HTTP }
    - { port: 443, comment: HTTPS }
    - { port: 8080, state: closed }
```

### yunohost_force_diskspace

Bypass the 10 GB minimum disk space requirement during postinstall

**_Type:_** boolean<br />

#### Default value

```YAML
yunohost_force_diskspace: false
```

### yunohost_ignore_dyndns

Do not subscribe to DynDNS during postinstall

**_Type:_** boolean<br />

#### Default value

```YAML
yunohost_ignore_dyndns: false
```

### yunohost_main_domain

Main domain used for postinstall and set as the YunoHost main domain

**_Type:_** string<br />

#### Default value

```YAML
yunohost_main_domain: ''
```

### yunohost_overwrite_root_password

Set the root password to match the admin password during postinstall

**_Type:_** boolean<br />

#### Default value

```YAML
yunohost_overwrite_root_password: true
```

### yunohost_permissions

List of app permissions to configure. Each entry: name (required, app.permission),
allowed (required, list of groups/users), label (str), show_tile (bool),
protected (bool), force (bool)

**_Type:_** list<br />

#### Default value

```YAML
yunohost_permissions: []
```

#### Example usage

```YAML
  yunohost_permissions:
    - name: nextcloud
      allowed: [all_users]
    - name: phpmyadmin
      allowed: [admins]
```

### yunohost_settings_email

Global email settings. Dependent settings (e.g. smtp_relay_enabled + smtp_relay_host)
must be in the same dict (pop3_enabled, smtp_relay_enabled, smtp_relay_host,
smtp_relay_port, smtp_relay_user, smtp_relay_password, etc.)

**_Type:_** dict<br />

#### Default value

```YAML
yunohost_settings_email: {}
```

### yunohost_settings_misc

Global miscellaneous settings (backup_compress_tar_archives, dns_exposure,
dns_custom_resolvers_enabled, tls_passthrough_enabled)

**_Type:_** dict<br />

#### Default value

```YAML
yunohost_settings_misc: {}
```

### yunohost_settings_security

Global security settings (admin_strength, ssh_port, ssh_password_authentication,
ssh_compatibility, nginx_redirect_to_https, nginx_compatibility, etc.)

**_Type:_** dict<br />

#### Default value

```YAML
yunohost_settings_security: {}
```

### yunohost_users

List of users to manage. Each entry: name (required), state (present/absent),
fullname, domain, password (required for creation), admin (bool),
mailbox_quota (str), mail_aliases (list), mail_forwards (list),
login_shell (str), purge (bool), update_password (on_create/always)

**_Type:_** list<br />

#### Default value

```YAML
yunohost_users: []
```

#### Example usage

```YAML
  yunohost_users:
    - name: john
      fullname: John Doe
      domain: example.com
      password: "{{ vault_john_password }}"
```

## Dependencies

None.

## License

GPL-2.0-or-later

## Author

plopoyop
