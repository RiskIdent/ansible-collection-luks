#!/usr/bin/python
# SPDX-FileCopyrightText: 2016-2018 Matt Davis <mdavis@ansible.com>
# SPDX-FileCopyrightText: 2018 Sam Doran <sdoran@redhat.com>
# SPDX-FileCopyrightText: 2022 Kalle Fagerberg <kalle.fagerberg@riskident.com>
# SPDX-FileCopyrightText: 2022 Risk.Ident GmbH <contact@riskident.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

# This script contains some modified snippets copied from
# https://github.com/ansible/ansible/blob/v2.12.6/lib/ansible/plugins/action/reboot.py
# taken at 2022-06-08.

from datetime import datetime
import os
import subprocess
import tempfile
import time

from ansible.errors import AnsibleActionFail
from ansible.module_utils._text import to_text
from ansible.plugins.action.reboot import (
    ActionModule as RebootActionModule,
    TimedOutException,
)
from ansible.utils.display import Display

display = Display()


class ActionModule(RebootActionModule):
    _VALID_ARGS = frozenset((
        *RebootActionModule._VALID_ARGS,

        # Required
        'luks_password',

        # Optional
        'luks_ssh_port',
        'luks_ssh_user',
        'luks_ssh_private_key_file',
        'luks_ssh_private_key',
        'luks_ssh_executable',
        'luks_ssh_connect_timeout',
        'luks_ssh_timeout',
        'luks_ssh_options',
        'post_unlock_delay',
        'luks_ssh_keygen_executable',
        'luks_ssh_add_executable',
        'luks_ssh_add_timeout',
    ))

    # These delays actually speed up the process, as w/o them the script will:
    # reboot machine, try unlock via SSH, wait out the SSH timeout (~60s),
    # auto-retry unlock via SSH, try ping via SSH, wait out the SSH timeout
    # (~60s), success! Totaling around 120s.
    #
    # With the delay the script will: reboot machine, sleep 10s, try unlock via
    # SSH, sleep 5s, try ping via SSH, success! Totaling around 20s.
    DEFAULT_POST_REBOOT_DELAY = 10  # reboot module has 0 as default
    DEFAULT_POST_UNLOCK_DELAY = 5

    DEFAULT_LUKS_SSH_PORT = 1024
    DEFAULT_LUKS_SSH_USER = "root"
    DEFAULT_LUKS_SSH_EXECUTABLE = "ssh"
    DEFAULT_LUKS_SSH_OPTIONS = [""]
    DEFAULT_LUKS_CONNECT_TIMEOUT = 600
    DEFAULT_LUKS_SSH_KEYGEN_EXECUTABLE = "ssh-keygen"
    DEFAULT_LUKS_SSH_ADD_EXECUTABLE = "ssh-add"
    DEFAULT_LUKS_SSH_ADD_TIMEOUT = 3600

    def try_get_connection_option(self, option):
        try:
            return self._connection.get_option(option)
        except KeyError:
            return None

    def get_task_arg(self, *names):
        for name in names:
            value = self._task.args.get(name)
            if value is not None:
                return value
        return None

    @property
    def connection_timeout(self):
        return self.try_get_connection_option('connection_timeout')

    @property
    def luks_password(self):
        return self.get_task_arg('luks_password')

    @property
    def luks_ssh_user(self):
        return self.get_task_arg("luks_ssh_user") or self.DEFAULT_LUKS_SSH_USER

    @property
    def luks_ssh_port(self):
        try:
            return int(self._task.args.get('luks_ssh_port', self.DEFAULT_LUKS_SSH_PORT))
        except ValueError as e:
            raise AnsibleActionFail("parse luks_ssh_port", orig_exc=e)

    @property
    def luks_ssh_private_key_file(self):
        return self.get_task_arg('luks_ssh_private_key_file') or self.try_get_connection_option('ansible_ssh_private_key_file')

    @property
    def luks_ssh_private_key(self):
        return self.get_task_arg('luks_ssh_private_key')

    @property
    def luks_ssh_executable(self):
        return self.get_task_arg("luks_ssh_executable") or self.try_get_connection_option("ansible_ssh_executable") or self.DEFAULT_LUKS_SSH_EXECUTABLE

    @property
    def luks_ssh_keygen_executable(self):
        return self.get_task_arg("luks_ssh_keygen_executable") or self.DEFAULT_LUKS_SSH_KEYGEN_EXECUTABLE

    @property
    def luks_ssh_add_executable(self):
        return self.get_task_arg("luks_ssh_add_executable") or self.DEFAULT_LUKS_SSH_ADD_EXECUTABLE

    @property
    def luks_ssh_add_timeout(self):
        return self.get_task_arg("luks_ssh_add_timeout") or self.DEFAULT_LUKS_SSH_ADD_TIMEOUT

    @property
    def luks_ssh_connect_timeout(self):
        luks_ssh_connect_timeout = self.get_task_arg(
            "luks_ssh_connect_timeout", "connect_timeout", "connect_timeout_sec")
        if luks_ssh_connect_timeout:
            try:
                return int(luks_ssh_connect_timeout)
            except ValueError as e:
                raise AnsibleActionFail(
                    "parse luks_ssh_connect_timeout", orig_exc=e)
        return None

    @property
    def luks_ssh_timeout(self):
        luks_ssh_timeout = self.get_task_arg(
            "luks_ssh_timeout", "reboot_timeout", "reboot_timeout_sec") or self.DEFAULT_REBOOT_TIMEOUT
        if luks_ssh_timeout:
            try:
                return int(luks_ssh_timeout)
            except ValueError as e:
                raise AnsibleActionFail(
                    "parse luks_ssh_timeout", orig_exc=e)
        return None

    @property
    def luks_ssh_options(self):
        luks_ssh_options = self.get_task_arg("luks_ssh_options")
        if not luks_ssh_options:
            return []
        if isinstance(luks_ssh_options, str):
            return [luks_ssh_options]
        return list(luks_ssh_options)

    @property
    def remote_addr(self):
        # Found by seeing _get_remote_addr in newer (after v2.13.0, unreleased) version,
        # https://github.com/ansible/ansible/blob/2f0530396b0bdb025c94b354cde95604ff1fd349/lib/ansible/plugins/action/__init__.py#L946
        # but in the older version I've installed it's this instead:
        # https://github.com/ansible/ansible/blob/v2.12.6/lib/ansible/plugins/action/__init__.py#L879
        return self._play_context.remote_addr

    @property
    def post_unlock_delay(self):
        return self.get_task_arg("post_unlock_delay") or self.DEFAULT_POST_UNLOCK_DELAY

    def get_luks_ssh_args(self):
        args = [
            self.luks_ssh_executable,
            '-p', str(self.luks_ssh_port),
        ]

        luks_ssh_options = self.luks_ssh_options
        for opt in luks_ssh_options:
            args.append('-o')
            args.append(opt)

        if not self.luks_ssh_private_key:
            # Only add "-i" flag if we don't rely on ssh-agent
            private_key_file = self.luks_ssh_private_key_file
            if private_key_file is not None:
                args.append('-i')
                args.append(private_key_file)

        luks_ssh_user = self.luks_ssh_user
        if luks_ssh_user is not None:
            args.append('-o')
            args.append('User=%s' % luks_ssh_user)

        luks_ssh_connect_timeout = self.luks_ssh_connect_timeout
        if luks_ssh_connect_timeout is not None:
            args.append('-o')
            args.append('ConnectTimeout=%d' % luks_ssh_connect_timeout)

        args.append(self.remote_addr)
        display.vvv("{action}: SSH connection args for LUKS: {args}".format(
            action=self._task.action, args=args))
        return args

    def run_luks_ssh_prompt(self, distribution):
        # Must have this distribution param as parent do_until_success_or_timeout
        # passes it explicitly, even though we don't need it.
        _ = distribution

        args = self.get_luks_ssh_args()
        try:
            display.vvv("{action}: Attempting LUKS SSH unlock via SSH exec".format(
                action=self._task.action))
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,  # capture STDOUT
                stderr=subprocess.STDOUT,  # redirect STDERR to STDOUT
                text=True,  # string input & output instead of bytes
                input=str(self.luks_password),
                check=True)  # raise error on non-0 exit code
            display.display("{action}: LUKS SSH unlock successful, output:\n\t{output}".format(
                action=self._task.action, output=result.stdout.replace("\n", "\n\t")))
        except subprocess.CalledProcessError as e:
            if e.returncode == 255:
                # SSH connection error; the machine is probably still booting.
                # Could also be any other SSH client errors, but we cannot
                # know that.
                display.warning("{action}: LUKS SSH connection fail (non-fatal, will attempt multiple times), output:\n\t{output}".format(
                    action=self._task.action, output=e.output.replace("\n", "\n\t")))
            else:
                display.warning("{action}: LUKS unlock disk-encryption via SSH prompt failed, output:\n{output}".format(
                    action=self._task.action, output=e.output))
            raise

    def unlock_luks(self, distribution):
        luks_ssh_timeout = self.luks_ssh_timeout
        result = {}
        display.vvv(
            "{action}: post-reboot: starting LUKS unlock retry loop".format(action=self._task.action))

        try:
            self.do_until_success_or_timeout(
                action=self.run_luks_ssh_prompt,
                action_desc="post-reboot unlock LUKS full-disk encryption",
                reboot_timeout=luks_ssh_timeout,
                distribution=distribution)
        except TimedOutException as e:
            result['failed'] = True
            result['rebooted'] = True
            result['unlocked'] = False
            result['msg'] = to_text(e)

        return result

    def set_result_elapsed(self, result: dict, start: datetime):
        elapsed = datetime.utcnow() - start
        result['elapsed'] = elapsed.seconds

    def run_reboot(self, distribution, previous_boot_time, task_vars):
        original_connection_timeout = self.connection_timeout
        reboot_result = self.perform_reboot(task_vars, distribution)

        if reboot_result.get('failed'):
            self.set_result_elapsed(reboot_result, reboot_result['start'])
            return reboot_result

        post_reboot_delay = self.post_reboot_delay
        if post_reboot_delay > 0:
            display.vvv("{action}: waiting an additional {delay} seconds (post_reboot_delay)".format(
                action=self._task.action, delay=post_reboot_delay))
            time.sleep(post_reboot_delay)

        unlock_result = self.unlock_luks(distribution)
        if unlock_result.get('failed'):
            self.set_result_elapsed(unlock_result, reboot_result['start'])
            return unlock_result

        post_unlock_delay = self.post_unlock_delay
        if post_unlock_delay > 0:
            display.vvv("{action}: waiting an additional {delay} seconds (post_unlock_delay)".format(
                action=self._task.action, delay=post_unlock_delay))
            time.sleep(post_unlock_delay)

        result = self.validate_reboot(distribution, original_connection_timeout, action_kwargs={
                                      'previous_boot_time': previous_boot_time})
        self.set_result_elapsed(result, reboot_result['start'])
        result['unlocked'] = True
        return result

    def validate_args(self):
        if not self.luks_password:
            raise AnsibleActionFail("luks_password is required")

    def setup_ssh_private_key_file(self):
        if self.luks_ssh_private_key_file:
            # Skip if we already have file
            return
        if not self.luks_ssh_private_key:
            raise AnsibleActionFail("luks_ssh_private_key_file or luks_ssh_private_key is required")

        private_key = self.luks_ssh_private_key
        public_key = self.private_key_to_public_key(private_key)
        if self.is_public_key_added_to_ssh_agent(public_key):
            # Skip as the key is already added
            return

        self.add_private_key_to_ssh_agent(private_key)

    def private_key_to_public_key(self, private_key: str):
        args = [
            self.luks_ssh_keygen_executable,
            "-y", # read private OpenSSH file, print OpenSSH public key
            "-f", "/dev/stdin", # read from STDIN (not Windows compatible!)
        ]
        try:
            display.vvv("{action}: Converting private key to public key via ssh-keygen".format(
                action=self._task.action))
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,  # capture STDOUT
                stderr=subprocess.STDOUT,  # redirect STDERR to STDOUT
                text=True,  # string input & output instead of bytes
                input=str(private_key),
                check=True)  # raise error on non-0 exit code
            return result.stdout
        except subprocess.CalledProcessError as e:
            display.warning("{action}: Failed converting SSH private key to public key, output:\n{output}".format(
                action=self._task.action, output=e.output))
            raise

    def is_public_key_added_to_ssh_agent(self, public_key: str):
        args = [
            self.luks_ssh_add_executable,
            "-T", # test if public key exists
            "/dev/stdin", # read from STDIN (not Windows compatible!)
        ]
        try:
            display.vvv("{action}: Checking if public key is added to ssh-agent via ssh-add".format(
                action=self._task.action))
            subprocess.run(
                args,
                stdout=subprocess.PIPE,  # capture STDOUT
                stderr=subprocess.STDOUT,  # redirect STDERR to STDOUT
                text=True,  # string input & output instead of bytes
                input=str(public_key),
                check=True)  # raise error on non-0 exit code
            return True
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                return False
            display.warning("{action}: Failed checking if SSH public key is added to ssh-agent, output:\n{output}".format(
                action=self._task.action, output=e.output))
            raise

    def add_private_key_to_ssh_agent(self, private_key: str):
        args = [
            self.luks_ssh_add_executable,
            "-t", str(self.luks_ssh_add_timeout),
            "-", # read from STDIN
        ]
        try:
            display.vvv("{action}: Adding private key to ssh-agent via ssh-add".format(
                action=self._task.action))
            subprocess.run(
                args,
                stdout=subprocess.PIPE,  # capture STDOUT
                stderr=subprocess.STDOUT,  # redirect STDERR to STDOUT
                text=True,  # string input & output instead of bytes
                input=str(private_key),
                check=True)  # raise error on non-0 exit code
        except subprocess.CalledProcessError as e:
            display.warning("{action}: Failed adding private key to ssh-agent via ssh-add, output:\n{output}".format(
                action=self._task.action, output=e.output))
            raise

    def run(self, tmp=None, task_vars=None):
        self._supports_check_mode = True
        self._supports_async = True

        # If running with local connection, fail so we don't reboot ourself
        if self._connection.transport == 'local':
            msg = 'Running {0} with local connection would reboot the control node.'.format(self._task.action)
            return {'changed': False, 'elapsed': 0, 'rebooted': False, 'failed': True, 'unlocked': False, 'msg': msg}

        if self._play_context.check_mode:
            return {'changed': True, 'elapsed': 0, 'rebooted': True, 'unlocked': True}

        if task_vars is None:
            task_vars = {}

        self.deprecated_args()

        result = super(RebootActionModule, self).run(tmp, task_vars)
        if result.get('skipped') or result.get('failed'):
            return result

        try:
            self.validate_args()
            self.setup_ssh_private_key_file()
        except AnsibleActionFail as e:
            result['failed'] = True
            result['reboot'] = False
            result['unlocked'] = False
            result['msg'] = to_text(e)
            return result

        if task_vars == None:
            task_vars = {}

        distribution = self.get_distribution(task_vars)

        try:
            previous_boot_time = self.get_system_boot_time(distribution)
        except Exception as e:
            result['failed'] = True
            result['reboot'] = False
            result['unlocked'] = False
            result['msg'] = to_text(e)
            return result

        return self.run_reboot(
            distribution, previous_boot_time, task_vars)
