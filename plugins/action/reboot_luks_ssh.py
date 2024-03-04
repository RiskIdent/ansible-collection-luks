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
# https://github.com/ansible/ansible/blob/v2.16.3/lib/ansible/plugins/action/reboot.py
# taken at 2024-02-21.

from datetime import datetime, timedelta, timezone
from random import random
import subprocess
import time

from ansible.errors import AnsibleActionFail
from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils._text import to_text
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.plugins.action.reboot import (
    ActionModule as RebootActionModule,
    TimedOutException,
)
from ansible.utils.display import Display

display = Display()


class StopRetryLoop(Exception):
    def __init__(self, exception: Exception):
        self.exception = exception
        super().__init__("StopRetryLoop: %s" % exception)


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
        'luks_stop_retry_on_output',
        'luks_manual_unlock_on_fail',
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
    DEFAULT_LUKS_STOP_RETRY_ON_OUTPUT = [
        "bad password",
        "maximum number of tries exceeded",
        "error",
        "timeout",
    ]
    DEFAULT_LUKS_SSH_RECONNECT_TIMEOUT = 3600
    DEFAULT_LUKS_MANUAL_UNLOCK_ON_FAIL = True

    _has_added_key_to_ssh_agent = False

    def _try_get_connection_option(self, option):
        try:
            return self._connection.get_option(option)
        except KeyError:
            return None

    def _get_task_arg(self, *names: str):
        for name in names:
            value = self._task.args.get(name)
            if value is not None:
                return value
        return None

    def _get_task_arg_int(self, *names: str):
        for name in names:
            value = self._task.args.get(name)
            if value is not None:
                try:
                    return int(value)
                except ValueError as e:
                    raise AnsibleActionFail(
                        "parse %s" % name, orig_exc=e)
        return None

    @property
    def connection_timeout(self):
        return self._try_get_connection_option('connection_timeout')

    @property
    def luks_password(self):
        return self._get_task_arg('luks_password')

    @property
    def luks_ssh_user(self):
        return self._get_task_arg("luks_ssh_user") or self.DEFAULT_LUKS_SSH_USER

    @property
    def luks_ssh_port(self):
        return self._get_task_arg_int('luks_ssh_port') or self.DEFAULT_LUKS_SSH_PORT

    @property
    def luks_ssh_private_key_file(self):
        return self._get_task_arg('luks_ssh_private_key_file') or self._try_get_connection_option('ansible_ssh_private_key_file')

    @property
    def luks_ssh_private_key(self):
        return self._get_task_arg('luks_ssh_private_key')

    @property
    def luks_ssh_executable(self):
        return self._get_task_arg("luks_ssh_executable") or self._try_get_connection_option("ansible_ssh_executable") or self.DEFAULT_LUKS_SSH_EXECUTABLE

    @property
    def luks_ssh_keygen_executable(self):
        return self._get_task_arg("luks_ssh_keygen_executable") or self.DEFAULT_LUKS_SSH_KEYGEN_EXECUTABLE

    @property
    def luks_ssh_add_executable(self):
        return self._get_task_arg("luks_ssh_add_executable") or self.DEFAULT_LUKS_SSH_ADD_EXECUTABLE

    @property
    def luks_ssh_add_timeout(self):
        return self._get_task_arg_int("luks_ssh_add_timeout") or self.DEFAULT_LUKS_SSH_ADD_TIMEOUT

    @property
    def luks_ssh_connect_timeout(self):
        return self._get_task_arg_int("luks_ssh_connect_timeout", "connect_timeout", "connect_timeout_sec")

    @property
    def luks_ssh_timeout(self):
        return self._get_task_arg_int("luks_ssh_timeout", "reboot_timeout", "reboot_timeout_sec") or self.DEFAULT_REBOOT_TIMEOUT

    @property
    def luks_ssh_reconnect_timeout(self):
        return self._get_task_arg_int("luks_ssh_reconnect_timeout") or self.DEFAULT_LUKS_SSH_RECONNECT_TIMEOUT

    @property
    def luks_ssh_options(self):
        luks_ssh_options = self._get_task_arg("luks_ssh_options")
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
        return self._get_task_arg("post_unlock_delay") or self.DEFAULT_POST_UNLOCK_DELAY

    @property
    def luks_stop_retry_on_output(self):
        return self._get_task_arg("luks_stop_retry_on_output") or self.DEFAULT_LUKS_STOP_RETRY_ON_OUTPUT

    @property
    def luks_manual_unlock_on_fail(self):
        # Cannot use "or" here to see if it's unset, as the data type is bool
        value = self._task.args.get('luks_manual_unlock_on_fail')
        if value is None:
            return self.DEFAULT_LUKS_MANUAL_UNLOCK_ON_FAIL
        return boolean(value)

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

    def run_luks_ssh_prompt(self, distribution, action_kwargs=None):
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
            output = str(e.output)
            if e.returncode == 255:
                # SSH connection error; the machine is probably still booting.
                # Could also be any other SSH client errors, but we cannot
                # know that.
                display.warning("{action}: LUKS SSH connection fail (non-fatal, will attempt multiple times), output:\n\t{output}".format(
                    action=self._task.action, output=output.replace("\n", "\n\t")))
            else:
                for substr in self.luks_stop_retry_on_output:
                    if substr.casefold() in output.casefold():
                        display.vvv("{action}: LUKS unlock disk-encryption via SSH prompt failed, known stop keywords founds, output:\n\t{output}".format(
                            action=self._task.action, output=output))
                        raise StopRetryLoop(e)

                display.warning("{action}: LUKS unlock disk-encryption via SSH prompt failed, output:\n\t{output}".format(
                    action=self._task.action, output=output))
            raise

    def unlock_luks(self, distribution, previous_boot_time, task_vars):
        display.vvv(
            "{action}: post-reboot: starting LUKS unlock retry loop".format(action=self._task.action))

        try:
            self.ri_do_until_success_or_timeout(
                action=self.run_luks_ssh_prompt,
                action_desc="post-reboot unlock LUKS full-disk encryption",
                distribution=distribution,
                reboot_timeout=self.luks_ssh_timeout)
            return {}

        except Exception as unlock_error:
            fail_result = {
                'failed': True,
                'rebooted': True,
                'unlocked': False,
                'msg': to_text(unlock_error),
            }
            if not self.luks_manual_unlock_on_fail:
                display.vvv("{action}: LUKS unlock failed. Not asking for manual unlock because luks_manual_unlock_on_fail was false".format(
                    action=self._task.action))
                return fail_result

            timeout = self.luks_ssh_reconnect_timeout
            hostname = self._get_remote_addr(task_vars)
            display.warning("{action}: LUKS unlock failed. Please unlock the host manually: {ansible_host} (timeout: {timeout} seconds)".format(
                action=self._task.action, ansible_host=hostname, timeout=timeout))

            try:
                self.do_until_success_or_timeout(
                    action=self.check_boot_time,
                    action_desc="post-reboot reconnect",
                    reboot_timeout=timeout,
                    distribution=distribution,
                    action_kwargs={'previous_boot_time': previous_boot_time})
                return {}

            except Exception:
                display.error("{action}: Timed out waiting for you to unlock host manually: {ansible_host} (timeout: {timeout} seconds)".format(
                    action=self._task.action, ansible_host=hostname, timeout=timeout))

                return fail_result

    def run_reconnect(self):
        self._connection.reset()

    def set_result_elapsed(self, result: dict, start: datetime):
        elapsed = datetime.now(timezone.utc) - start
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

        unlock_result = self.unlock_luks(
            distribution, previous_boot_time, task_vars)
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
        private_key = self.luks_ssh_private_key
        if not private_key:
            raise AnsibleActionFail(
                "luks_ssh_private_key_file or luks_ssh_private_key is required")

        self.add_private_key_to_ssh_agent(private_key)
        self._has_added_key_to_ssh_agent = True

    def add_private_key_to_ssh_agent(self, private_key: str):
        args = [
            self.luks_ssh_add_executable,
            "-t", str(self.luks_ssh_add_timeout),
            "-",  # read from STDIN
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
            raise RuntimeError("Failed adding private key to ssh-agent via ssh-add, output:\n{output}".format(
                output=e.output)) from e

    def remove_public_key_from_ssh_agent(self, public_key: str):
        args = [
            self.luks_ssh_add_executable,
            "-d",
            "-",  # read from STDIN
        ]
        try:
            display.vvv("{action}: Removing private key from ssh-agent via ssh-add".format(
                action=self._task.action))
            subprocess.run(
                args,
                stdout=subprocess.PIPE,  # capture STDOUT
                stderr=subprocess.STDOUT,  # redirect STDERR to STDOUT
                text=True,  # string input & output instead of bytes
                input=str(public_key),
                check=True)  # raise error on non-0 exit code
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Failed removing private key from ssh-agent via ssh-add, output:\n{output}".format(
                output=e.output)) from e

    def private_key_to_public_key(self, private_key: str):
        args = [
            self.luks_ssh_keygen_executable,
            "-y",  # read private OpenSSH file, print OpenSSH public key
            "-f", "/dev/stdin",  # read from STDIN (not Windows compatible!)
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
            raise RuntimeError("Failed converting SSH private key to public key, output:\n{output}".format(
                output=e.output)) from e

    def ri_do_until_success_or_timeout(self, action, reboot_timeout, action_desc, distribution, action_kwargs=None):
        # RiskIdent: This function is taken directly from the ansible.builtin.reboot code
        # Changed sections are marked with a "# RiskIdent:" line comment

        max_end_time = datetime.now(timezone.utc) + timedelta(seconds=reboot_timeout)
        if action_kwargs is None:
            action_kwargs = {}

        fail_count = 0
        max_fail_sleep = 12
        last_error_msg = ''

        while datetime.now(timezone.utc) < max_end_time:
            try:
                action(distribution=distribution, **action_kwargs)
                if action_desc:
                    display.debug('{action}: {desc} success'.format(
                        action=self._task.action, desc=action_desc))
                return
            except StopRetryLoop as e:
                # RiskIdent: This additional "except" statement is all that's added
                raise e.exception
            except Exception as e:
                if isinstance(e, AnsibleConnectionFailure):
                    try:
                        self._connection.reset()
                    except AnsibleConnectionFailure:
                        pass
                # Use exponential backoff with a max timeout, plus a little bit of randomness
                random_int = random.randint(0, 1000) / 1000
                fail_sleep = 2 ** fail_count + random_int
                if fail_sleep > max_fail_sleep:

                    fail_sleep = max_fail_sleep + random_int
                if action_desc:
                    try:
                        error = to_text(e).splitlines()[-1]
                    except IndexError as e:
                        error = to_text(e)
                    last_error_msg = f"{self._task.action}: {action_desc} fail '{error}'"
                    msg = f"{last_error_msg}, retrying in {fail_sleep:.4f} seconds..."

                    display.debug(msg)
                    display.vvv(msg)
                fail_count += 1
                time.sleep(fail_sleep)

        if last_error_msg:
            msg = f"Last error message before the timeout exception - {last_error_msg}"
            display.debug(msg)
            display.vvv(msg)
        raise TimedOutException('Timed out waiting for {desc} (timeout={timeout})'.format(
            desc=action_desc, timeout=reboot_timeout))

    def cleanup(self, force=False):
        if self._has_added_key_to_ssh_agent:
            try:
                public_key = self.private_key_to_public_key(
                    str(self.luks_ssh_private_key))
                self.remove_public_key_from_ssh_agent(public_key)
                self._has_added_key_to_ssh_agent = False
            except Exception as e:
                display.warning("{action}: Failed cleaning up SSH key from SSH-agent, error:\n{error}".format(
                    action=self._task.action, error=e))

        super(ActionModule, self).cleanup(force=force)

    def run(self, tmp=None, task_vars=None):
        self._supports_check_mode = True
        self._supports_async = True

        # If running with local connection, fail so we don't reboot ourself
        if self._connection.transport == 'local':
            msg = 'Running {0} with local connection would reboot the control node.'.format(
                self._task.action)
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

        if task_vars is None:
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
