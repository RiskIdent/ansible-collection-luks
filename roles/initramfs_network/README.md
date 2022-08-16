<!--
SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>

SPDX-License-Identifier: CC-BY-4.0
-->

# initramfs_network

Installs initramfs-tools-network-hook (<https://github.com/stcz/initramfs-tools-network-hook>)
to configure "bond" and "vlan" devices in an initramfs boot partition, as well
as the server's static IP during initramfs.

## Requirements

- On the remote:

  - `apt`, as this role is using [`ansible.builtin.apt`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/apt_module.html#requirements)

  - `tar`, to extract downloaded tarball of <https://github.com/stcz/initramfs-tools-network-hook>

  - `initramfs` set up, such as by enabling LUKS full-disk encryption
    when installing the OS.

  - Requirements from <https://github.com/stcz/initramfs-tools-network-hook>:

    - Package `iproute2` for bond support
      (installed if `initramfs_network_install_iproute2` is set to `true`)

    - Package `vlan` for vlan support
      (installed if `initramfs_network_install_vlan` is set to `true`)

## Role Variables

See [`./defaults/main.yml`](./defaults/main.yml)

## Example Playbook

```yaml
- hosts: servers
  roles:
     - { role: initramfs_network, tags: initramfs_network }
```

## Known issues

- When using bonding, especially the 802.3ad mode (default),
  only bonding a single interface will sometimes cause issues.

  If you insist on using bonding on a single interface then you can try
  overriding `initramfs_network_bond_driver_options` to set the bonding mode
  to e.g balance-rr, which has previously proven successful in this scenario:

  ```yaml
  initramfs_network_bond_driver_options: "mode=balance-rr miimon=100"
  ```
