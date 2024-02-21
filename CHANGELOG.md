<!--
SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>

SPDX-License-Identifier: CC-BY-4.0
-->

# Risk.Ident's LUKS Ansible collection changelog

This project tries to follow [SemVer 2.0.0](https://semver.org/).

<!--
	When composing new changes to this list, try to follow convention.
	The WIP release shall be updated just before adding the Git tag.
	Replace (WIP) by (YYYY-MM-DD), e.g. (2021-02-09) for 9th of Febuary, 2021
	A good source on conventions can be found here:
	https://changelog.md/
-->

## v0.3.1 (WIP)

- Fixed TypeError on datetime variables that were preventing the `reboot_luks_ssh` action plugin to succeeds in rebooting. (#20)

## v0.3.0 (2023-01-18)

- Added "manual unlock" feature, where you have to manually unlock the machine
  if the `reboot_luks_ssh` action plugin succeeds in rebooting,
  but fails to unlock it. (#15)

- Added settings for cryptsetup-unlock output to consider failed unlock,
  and will fail early instead of keep retrying an incorrect password. (#15)

- Added args: (#15)

  - `luks_stop_retry_on_output`
  - `luks_manual_unlock_on_fail`

- Added missing documentation on args added in #13. (#15)

## v0.2.0 (2022-11-02)

- Added support for "check mode". (#12)

- Added field `luks_ssh_private_key` for supplying SSH private key as
  raw string instead of using `luks_ssh_private_key_file`. (#13)

  This is implemented by adding the private key to your ssh-agent, and removing
  it during the task's cleanup (when the task fails, is aborted, or finished).
  The key is added by default with the `-t 3600` flag, so the key is
  automatically removed from your ssh-agent after 1 hour, as a fallback if the
  cleanup fails.

## v0.1.1 (2022-08-29)

- Added `meta/runtime.yml` (#7)

- Fixed missing quotes in `dropbear_ssh_pub_keys_unlock_options` default SSH
  restriction command in `initramfs_dropbear` role. (#8)

- Added `become: yes` to documentation, as all this collection's roles and
  action plugins need it. (#9)

- Added docs to introduce action plugin and roles to README.md (#11)

## v0.1.0 (2022-08-23)

- Added repository to GitHub, moved from our closed-source internal repo. (#1)
