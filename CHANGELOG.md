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

## v0.1.1 (2022-08-29)

- Added `meta/runtime.yml` (#7)

- Fixed missing quotes in `dropbear_ssh_pub_keys_unlock_options` default SSH
  restriction command in `initramfs_dropbear` role. (#8)

- Added `become: yes` to documentation, as all this collection's roles and
  action plugins need it. (#9)

- Added docs to introduce action plugin and roles to README.md (#11)

## v0.1.0 (2022-08-23)

- Added repository to GitHub, moved from our closed-source internal repo. (#1)
