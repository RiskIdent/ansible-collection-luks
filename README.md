<!--
SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>

SPDX-License-Identifier: CC-BY-4.0
-->

# Ansible Collection - riskident.luks

[![REUSE status](https://api.reuse.software/badge/github.com/RiskIdent/ansible-collection-luks)](https://api.reuse.software/info/github.com/RiskIdent/ansible-collection-luks)

Ansible roles to install Dropbear and configure initramfs networking, a
precondition for the action plugin `reboot_luks_ssh` to automatically reboot a
machine with LUKS (Linux Unified Key Setup) full-disk encryption enabled.

Useful for self-hosted machines that are protected with LUKS full-disk
encryption, but you still want to be able to perform fully automatic system
updates.

## Action plugins

### reboot\_luks\_ssh

Reboots a machine, and after the reboot it tries to connect to the server via
SSH to unlock the LUKS full-disk encryption.

Example usage:

```yaml
- hosts: servers
  become: true # need sudo access to reboot
  tasks:
    - name: Upgrade all apt packages
      ansible.builtin.apt:
        upgrade: dist
        force_apt_get: true

    - name: Reboot
      riskident.luks.reboot_luks_ssh:
        # disk_encrypt_password is an arbitrary variable you need to
        # specify somewhere, such as in an ansible-vault encrypted file
        luks_password: "{{ disk_encrypt_password }}"
```

Built on top of the [`ansible.builtin.reboot`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/reboot_module.html)
module, so it supports all parameters from that module, in addition to some
that are specific to this module.

Read more: [./docs/reboot_luks_ssh.md](./docs/reboot_luks_ssh.md)

## Roles

### initramfs\_dropbear

Installs and configures [Dropbear](https://matt.ucc.asn.au/dropbear/dropbear.html),
which is a lightweight SSH server that is suitable for embedding inside the
initramfs partition to allow running cryptroot-unlock remotely.

Example playbook:

```yaml
- hosts: my_machine
  become: true
  roles:
     - { role: initramfs_dropbear, tags: initramfs_dropbear }
```

Example variables:

```yaml
# variables, e.g in host_vars/my_machine/initramfs_dropbear.yml

dropbear_ssh_pub_keys_unlock:
  - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQChqH7z(etc...)

dropbear_port: 22
```

Read more: [./roles/initramfs_dropbear/README.md](./roles/initramfs_dropbear/README.md)

### initramfs\_network

Allows configuration of:

- Device bonding
- VLAN configuration
- Static IP, netmask, and gateway IP configuration

To be applied in an initramfs boot partition. Useful to make sure Dropbear from
above `initramfs_dropbear` role is properly available inside your network, and
so that the `reboot_luks_ssh` action plugin can reach the machine.

Example playbook:

```yaml
- hosts: my_machine
  become: true
  roles:
     - { role: initramfs_network, tags: initramfs_network }
```

Example variables:

```yaml
# variables, e.g in host_vars/my_machine/initramfs_network.yml

initramfs_network_device_ips:
  - name: bond0.123
    cidr: 192.168.1.23/24
    gateway_ip: 192.168.1.1

initramfs_network_bonds:
  - name: bond0
    interfaces: [ eth0, eth1 ]

initramfs_network_vlans:
  - link: bond0
    id: 123
```

Read more: [./roles/initramfs_network/README.md](./roles/initramfs_network/README.md)

## License

This repository complies with the [REUSE recommendations](https://reuse.software/).

Different licenses are used for different files. In general:

- Code, such as Ansible roles and action plugins are licensed under
  GNU General Public License v3.0 or later ([LICENSES/GPL-3.0-or-later.txt](LICENSES/GPL-3.0-or-later.txt)).

- Documentation licensed under Creative Commons Attribution 4.0 International ([LICENSES/CC-BY-4.0.txt](LICENSES/CC-BY-4.0.txt)).

- Miscellaneous files, e.g `.gitignore`, are licensed under CC0 1.0 Universal ([LICENSES/CC0-1.0.txt](LICENSES/CC0-1.0.txt)).

Please see each file's header or accompanied `.license` file for specifics.
