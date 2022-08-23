<!--
SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>

SPDX-License-Identifier: CC-BY-4.0
-->

# Contributing guide

## Adding changes

1. Make your changes in a new branch

2. Update [`CHANGELOG.md`](./CHANGELOG.md), if the change is user-affecting
   (docs changes or lint fixes don't have to cause changelog/version bumps)

   - Ensure correct version bump to a `(WIP)` (Work In Progress) version.

   - Always compare to the latest **released** version for if it should be a
     major, minor, or patch version bump, according to [SemVer 2.0.0](https://semver.org/).

   - Add a new version with `(WIP)` instead of date, if none exists. There
     should always be **at most** 1 `(WIP)` version.

3. Update version in [`galaxy.yml`](./galaxy.yml) if it's out of date.

4. Create a PR targeting `main` branch.

## Publishing a version

1. Ensure version in [`galaxy.yml`](./galaxy.yml) is up to date with what's
   latest in [`CHANGELOG.md`](./CHANGELOG.md).

2. Change `(WIP)` in `CHANGELOG.md` to today's date, in
   `(YYYY-MM-DD)` format. E.g `(2022-08-23)`.

3. Commit and push to new branch, e.g `release/0.1.0`, and create a PR.

4. Wait until after PR has been merged into `main` before continuing.

5. Build the collection tarball.

   ```console
   Always good practice to make sure you're on the latest commit:
   $ git checkout main
   $ git pull

   $ make
   Building 0.1.0
   ansible-galaxy collection build --force
   Created collection for riskident.luks at riskident-luks-0.1.0.tar.gz
   ```

6. Upload tarball to Ansible Galaxy namespace [`riskident`](https://galaxy.ansible.com/riskident).

   Can be done via command line or via website. Docs: <https://docs.ansible.com/ansible/devel/dev_guide/developing_collections_distributing.html#publishing-your-collection>

7. Create release: <https://github.com/RiskIdent/ansible-collection-luks/releases/new>

   - "Choose a tag": enter version, e.g `0.1.0`, and click <kbd>+ Create new tag: 0.1.0 on publish</kbd>
   - Paste the release notes from the `CHANGELOG.md` into the description
   - Click <kbd>Publish release</kbd>
