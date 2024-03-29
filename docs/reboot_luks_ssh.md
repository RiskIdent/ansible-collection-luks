<!--
SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>

SPDX-License-Identifier: CC-BY-4.0
-->

# Reboot LUKS-enabled machine via SSH

Extension of [`ansible.builtin.reboot`](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/reboot_module.html)
that also unlocks LUKS (Linux Unified Key Setup) full-disk encryption.

This assumes your LUKS boot menu also runs an SSH server to allow entering
the disk encryption password remotely.

## Limitations

- If using Dropbear v2019.x or older (such as on Ubuntu 20.04):

  - Only RSA SSH keys are supported. No ed25519 keys can be used to unlock
    the LUKS. Support for ed25519 was first added in Dropbear v2020.79.

  - You need to add `PubkeyAcceptedKeyTypes +ssh-rsa` to the `luks_ssh_options`
    setting. Due to new crypto standards, your SSH client may reject Dropbear's
    public key. Using an older version of Dropbear with a newer version of an
    SSH client will produce conflicts. The mentioned option will resolve this.

  If using Dropbear v2020.79 or newer (such as on Ubuntu 22.04), then you don't
  need to worry about this. (Changelog: <https://matt.ucc.asn.au/dropbear/CHANGES>)

- Does not work if the target machine has already been rebooted and is in the
  LUKS boot, awaiting to be unlocked by the disk-encryption passwords.

  This is more of a limitation with Ansible than with this action plugin, as
  ansible requires to be able to contact the remote machine to gather facts and
  to just ping it to make sure it has SSH access.

- Only supports one main encrypted partition. Subsequent LUKS decryptions can
  be chained using `/etc/crypttab` and key files on original encrypted
  partition.

- Does not distinguish connection errors with other SSH errors. E.g: if the
  `luks_ssh_private_key_file` points to a path that does not exist.
  These errors are swallowed and are only visible if you supply the `-vvv` flag
  to the ansible/ansible-playbook command.

- When using `luks_ssh_private_key` (instead of `luks_ssh_private_key_file`)
  then this action plugin will assume you have an ssh-agent running.
  It will add the private key to your agent at the beginning of the task and
  clean up at the end.

  It will always try to remove the `luks_ssh_private_key` after the task,
  no matter if it was registered there before or not. Do not reuse an SSH key
  in the task that you would normally have added to your local ssh-agent,
  or be prepared to `ssh-add` it back again after running this action plugin
  when you need it for a manual SSH operation.

## Requirements

Target machines must run an SSH server on boot to allow entering the LUKS
password remotely.

Such as by using [Dropbear](https://matt.ucc.asn.au/dropbear/dropbear.html).

A role to install Dropbear into the initramfs can be found at
[../../roles/initramfs\_dropbear](../../roles/initramfs_dropbear/README.md)

When using `luks_ssh_private_key` (instead of `luks_ssh_private_key_file`),
an ssh-agent must be running on the control-node
(the machine that runs Ansible).

### Installing Dropbear

(This is installed on the remote target machines that has LUKS full-disk
encryption enabled)

```sh
sudo apt install dropbear-initramfs -y
```

Edit the Dropbear config (as root):

- `/etc/dropbear-initramfs/config` (Ubuntu 20.04)
- `/etc/dropbear/initramfs/dropbear.conf` (Ubuntu 22.04)

```config
# -j                  Disable local port forwarding.
# -k                  Disable remote port forwarding.
# -p [address:]port   Listen on specified address and TCP port.
DROPBEAR_OPTIONS="-jk -p 1024"
```

Add SSH public key to the `authorized_keys` file:

- `/etc/dropbear-initramfs/authorized_keys` (Ubuntu 20.04, Debian 11.3)
- `/etc/dropbear/initramfs/authorized_keys` (Ubuntu 22.04)

> :warning: Must be RSA key if using Dropbear v2019.78 or older! Support for
> ed25519 keys was first added in Dropbear v2020.79, which is shipped first in
> Ubuntu 22.04

Prepend line in `authorized_keys` with
`command="/usr/bin/cryptroot-unlock",no-port-forwarding,no-X11-forwarding`
to restrict the SSH access, for security reasons.

E.g:

```text
command="/usr/bin/cryptroot-unlock",no-port-forwarding,no-X11-forwarding,no-pty ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCctMnwxmy0Gme1fSzAjm38caHgv54YBdAh+G1zbhTKa96xJUdZ5mJGfFL07z49RwKDeg3v8xpx1EpW7FxSKPFjMeIkVIFnblqRCG3+IEN8ngXpL81HudoWEpRrcq/Q1puxUsNmrROqbD9IaVIUPvcyyeVWo/aD97V3OxvDUmEDsuuLaMortcIGAhgbIjjymKxy6gE7RQaFSeX+ql8WkpsxC/Fa3mM83oy8k+8nxw89mBgXeF6wMcbcuujFIJLQduvdVbL5r0Go8Z3DKTwIR1OzGqlKgeAyuE6L3QZ4IWqu1RlcfJGrE0jSZ/ZGFotikzM8K/KtQZoQJLv1tHepenqXNE6ztyNd2VCgwGnhLxnGrjc91YBi/lnxTr9xEF1RqFyf+nKTcbsuz4/QghXejF4e1vGxiCj+SiEi/XryG32p8T8zO+X+8Ymp2oZo9QxoD5RQmL0VgfXePR3AO62hVIM9wIQlHCT1qlXbMrzRXVjvsCIrD6NGTncOF/d0tsFudtU= Sample RSA key to access LUKS boot
```

Don't forget to refresh the LUKS boot:

```sh
sudo update-initramfs -u
```

## Parameters

All parameters from the `ansible.builtin.reboot` module are supported:
<https://docs.ansible.com/ansible/latest/collections/ansible/builtin/reboot_module.html#parameters>

In addition, `reboot_luks_ssh` also defines some additional parameters:

### Required parameters

| Parameter      | Type   | Comments |
| -------------  | ------ | -------- |
| luks\_password | string | LUKS disk encryption password.

### Optional parameters

<!--lint disable maximum-line-length-->

| Parameter                    | Type   | Default | Comments |
| ---------------------------- | ------ | ------- | -------- |
| `luks_ssh_port`              | int    | `1024` | SSH port of target machine when in LUKS boot (Dropbear)
| `luks_ssh_user`              | string | `"root"` | SSH username used when connecting to LUKS boot (Dropbear)
| `luks_ssh_private_key_file`  | string | `ansible_ssh_private_key_file` (inventory param) | Path of SSH private key file, e.g `/home/ubuntu/.ssh/id_rsa`
| `luks_ssh_private_key`       | string | `""` | Raw SSH private key text, e.g the content of your `~/.ssh/id_rsa` file
| `luks_ssh_executable`        | string | `ansible_ssh_executable` (inventory param), or `"ssh"` | Command name of SSH executable used when connecting to LUKS boot (Dropbear)
| `luks_ssh_connect_timeout`   | int    | `connect_timeout` (`ansible.builtin.reboot` param), or `600` | Connection timeout (in seconds) used when connecting to LUKS boot (Dropbear)
| `luks_ssh_timeout`           | int    | `reboot_timeout` (`ansible.builtin.reboot` param) | Connection timeout (in seconds) for all connection retries in total, including the wait time between the retries.
| `luks_ssh_options`           | list\[string] | `[]` | Additional arbitrary SSH options used when connecting to LUKS boot (Dropbear), such as `PubkeyAcceptedKeyTypes`
| `post_unlock_delay`          | int    | `0` | Time to wait (in seconds) after a successful LUKS unlock.
| `luks_ssh_keygen_executable` | string | `"ssh-keygen"` | The `ssh-keygen` executable to use when converting `luks_ssh_private_key` to a public key.
| `luks_ssh_add_executable`    | string | `"ssh-add"` | The `ssh-add` executable to use when adding the `luks_ssh_private_key` to your SSH agent.
| `luks_ssh_add_timeout`       | int    | `3600` | The `luks_ssh_private_key` key is automatically removed by the SSH agent after this many seconds, in case the `reboot_luks_ssh` action plugin fails to remove it by itself.
| `luks_stop_retry_on_output`  | list\[string] | `["bad password", "maximum number of tries exceeded", "error", "timeout"]` | If the cryptroot-unlock's output contains any of these substrings (case insensitive) then stop retrying to unlock and fail early.
| `luks_ssh_reconnect_timeout` | int    | `3600` | Timeout for reconnecting after failing to unlock, waiting for manual unlock by human.
| `luks_manual_unlock_on_fail` | bool   | `true` | If true, the action plugin will prompt the human to manually unlock LUKS if the action plugin fails, instead of failing the task.

<!--lint enable maximum-line-length-->

## Example Playbook

```yaml
- hosts: servers
  become: true # need sudo access to reboot
  tasks:
    - name: Reboot
      reboot_luks_ssh:
        # disk_encrypt_password is an arbitrary variable you need to
        # specify somewhere
        luks_password: "{{ disk_encrypt_password }}"

    - name: Reboot with custom port and user
      reboot_luks_ssh:
        luks_password: "{{ disk_encrypt_password }}"
        luks_ssh_port: 22
        luks_ssh_user: admin
        luks_ssh_timeout: 600

    - name: Reboot with custom options
      reboot_luks_ssh:
        luks_password: "{{ disk_encrypt_password }}"
        luks_ssh_options:
          - "PubkeyAcceptedKeyTypes +ssh-rsa"
          - "ProxyJump 10.0.1.2"
```

## Return values

Same return values as `ansible.builtin.reboot`:
<https://docs.ansible.com/ansible/latest/collections/ansible/builtin/reboot_module.html#return-values>

<!--lint disable maximum-line-length-->

| Key      | Type    | Sample | Returned | Description |
| -------- | ------- | ------ | -------- | ----------- |
| elapsed  | int     | `23`   | always   | The number of seconds that elapsed waiting for the system to be rebooted.
| rebooted | boolean | `true` | always   | true if the machine was rebooted.

<!--lint enable maximum-line-length-->

In addition, `reboot_luks_ssh` also defines some additional return values:

<!--lint disable maximum-line-length-->

| Key      | Type    | Sample | Returned | Description |
| -------- | ------- | ------ | -------- | ----------- |
| unlocked | boolean | `true` | always   | true if the disk encryption was unlocked.

<!--lint enable maximum-line-length-->
