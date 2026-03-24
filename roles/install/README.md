# install

 Install YunoHost on a fresh Debian 12 (Bookworm) system.
Converted from the official install script at https://install.yunohost.org/.
This role performs all steps up to (but not including) the post-installation.

## Table of contents

- [Requirements](#requirements)
- [Default Variables](#default-variables)
  - [yunohost_install_conflicting_packages](#yunohost_install_conflicting_packages)
  - [yunohost_install_debconf_preseeds](#yunohost_install_debconf_preseeds)
  - [yunohost_install_debian_codename](#yunohost_install_debian_codename)
  - [yunohost_install_distrib](#yunohost_install_distrib)
  - [yunohost_install_force](#yunohost_install_force)
  - [yunohost_install_gpg_key_url](#yunohost_install_gpg_key_url)
  - [yunohost_install_packages](#yunohost_install_packages)
  - [yunohost_install_pre_upgrade_packages](#yunohost_install_pre_upgrade_packages)
  - [yunohost_install_predeps](#yunohost_install_predeps)
  - [yunohost_install_repo_url](#yunohost_install_repo_url)
  - [yunohost_install_upgrade_system](#yunohost_install_upgrade_system)
- [Dependencies](#dependencies)
- [License](#license)
- [Author](#author)

---

## Requirements

- Minimum Ansible version: `2.15`

## Default Variables

### yunohost_install_conflicting_packages

#### Default value

```YAML
yunohost_install_conflicting_packages:
  - bind9
  - apache2
```

### yunohost_install_debconf_preseeds

#### Default value

```YAML
yunohost_install_debconf_preseeds:
  slapd:
    no_log: true
    entries:
      - {question: slapd/password1, value: yunohost, vtype: password}
      - {question: slapd/password2, value: yunohost, vtype: password}
      - {question: slapd/domain, value: yunohost.org, vtype: string}
      - {question: shared/organization, value: yunohost.org, vtype: string}
      - {question: slapd/allow_ldap_v2, value: 'false', vtype: boolean}
      - {question: slapd/invalid_config, value: 'true', vtype: boolean}
      - {question: slapd/backend, value: MDB, vtype: select}
  postfix:
    no_log: false
    entries:
      - {question: postfix/main_mailer_type, value: Internet Site, vtype: select}
      - {question: postfix/mailname, value: /etc/mailname, vtype: string}
  nslcd:
    no_log: true
    entries:
      - {question: nslcd/ldap-bindpw, value: '', vtype: password}
      - {question: nslcd/ldap-starttls, value: 'false', vtype: boolean}
      - {question: nslcd/ldap-reqcert, value: '', vtype: select}
      - {question: nslcd/ldap-uris, value: ldap://localhost/, vtype: string}
      - {question: nslcd/ldap-binddn, value: '', vtype: string}
      - {question: nslcd/ldap-base, value: 'dc=yunohost,dc=org', vtype: string}
  libnss-ldapd:
    no_log: false
    entries:
      - {question: libnss-ldapd/nsswitch, value: 'group, passwd, shadow', vtype:
          multiselect}
  postsrsd:
    no_log: false
    entries:
      - {question: postsrsd/domain, value: yunohost.org, vtype: string}
```

### yunohost_install_debian_codename

Debian codename to target

**_Type:_** string<br />

#### Default value

```YAML
yunohost_install_debian_codename: bookworm
```

### yunohost_install_distrib

YunoHost distribution channel

**_Type:_** string<br />

#### Default value

```YAML
yunohost_install_distrib: stable
```

### yunohost_install_force

Skip pre-flight checks (docker detection, bind9/apache2 conflict)

**_Type:_** boolean<br />

#### Default value

```YAML
yunohost_install_force: false
```

### yunohost_install_gpg_key_url

YunoHost GPG key URL (used by deb822_repository signed_by)

**_Type:_** string<br />

#### Default value

```YAML
yunohost_install_gpg_key_url: https://forge.yunohost.org/yunohost_bookworm.asc
```

### yunohost_install_packages

#### Default value

```YAML
yunohost_install_packages:
  - yunohost
  - yunohost-admin
  - postfix
```

### yunohost_install_pre_upgrade_packages

#### Default value

```YAML
yunohost_install_pre_upgrade_packages:
  - libtext-iconv-perl
  - grub-common
  - grub2-common
```

### yunohost_install_predeps

#### Default value

```YAML
yunohost_install_predeps:
  - lsb-release
  - dialog
  - curl
  - gnupg
  - apt-transport-https
  - adduser
  - debconf
  - debconf-utils
  - debhelper
  - dh-autoreconf
  - locales
  - python3-debian
```

### yunohost_install_repo_url

YunoHost Debian repository base URL

**_Type:_** string<br />

#### Default value

```YAML
yunohost_install_repo_url: http://forge.yunohost.org/debian/
```

### yunohost_install_upgrade_system

Perform a full dist-upgrade before installing YunoHost

**_Type:_** boolean<br />

#### Default value

```YAML
yunohost_install_upgrade_system: true
```

## Dependencies

None.

## License

GPL-2.0-or-later

## Author

plopoyop
