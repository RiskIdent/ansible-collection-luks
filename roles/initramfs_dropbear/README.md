<!--
SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>

SPDX-License-Identifier: CC-BY-4.0
-->

# initramfs\_dropbear

Installs Dropbear, a lightweight SSH server, into the initramfs boot partition.

Use case: Unlock a LUKS (Linux Unified Key Setup) full-disk encrypted root
partition remotely via SSH.

This role ensures that Dropbear is correctly installed and will be serving a
securely configured SSH server that only allows unlocking the LUKS, and nothing
else.

## Requirements

- On the remote:

  - `apt`, as this role is using [`ansible.builtin.apt`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/apt_module.html#requirements)

  - `initramfs` already set up with LUKS boot partition, such as by enabling
    full-disk encryption when installing the OS.

## Role Variables

See [`./defaults/main.yml`](./defaults/main.yml)

## Example Playbook

```yaml
- hosts: servers
  become: true
  roles:
     - { role: initramfs_dropbear, tags: initramfs_dropbear }
```
