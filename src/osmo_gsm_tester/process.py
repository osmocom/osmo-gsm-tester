# osmo_gsm_tester: process management
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import subprocess
import signal

from . import log
from .util import Dir

class Process(log.Origin):

    process_obj = None
    outputs = None
    result = None
    killed = None

    def __init__(self, name, run_dir, popen_args, **popen_kwargs):
        self.name_str = name
        self.set_name(name)
        self.set_log_category(log.C_RUN)
        self.run_dir = run_dir
        self.popen_args = popen_args
        self.popen_kwargs = popen_kwargs
        self.outputs = {}
        if not isinstance(self.run_dir, Dir):
            self.run_dir = Dir(os.path.abspath(str(self.run_dir)))

    def set_env(self, key, value):
        env = self.popen_kwargs.get('env') or {}
        env[key] = value
        self.popen_kwargs['env'] = env

    def make_output_log(self, name):
        '''
        create a non-existing log output file in run_dir to pipe stdout and
        stderr from this process to.
        '''
        path = self.run_dir.new_child(name)
        f = open(path, 'w')
        self.dbg(path)
        f.write('(launched: %s)\n' % time.strftime(log.LONG_DATEFMT))
        f.flush()
        self.outputs[name] = (path, f)
        return f

    def launch(self):
        with self:

            self.dbg('cd %r; %s %s' % (
                    os.path.abspath(str(self.run_dir)),
                    ' '.join(['%s=%r'%(k,v) for k,v in self.popen_kwargs.get('env', {}).items()]),
                    ' '.join(self.popen_args)))

            self.process_obj = subprocess.Popen(
                self.popen_args,
                stdout=self.make_output_log('stdout'),
                stderr=self.make_output_log('stderr'),
                shell=False,
                cwd=self.run_dir.path,
                **self.popen_kwargs)
            self.set_name(self.name_str, pid=self.process_obj.pid)
            self.log('Launched')

    def _poll_termination(self, time_to_wait_for_term=5):
        wait_step = 0.001
        waited_time = 0
        while True:
            # poll returns None if proc is still running
            self.result = self.process_obj.poll()
            if self.result is not None:
                return True
            waited_time += wait_step
            # make wait_step approach 1.0
            wait_step = (1. + 5. * wait_step) / 6.
            if waited_time >= time_to_wait_for_term:
                break
            time.sleep(wait_step)
        return False

    def terminate(self):
        if self.process_obj is None:
            return
        if self.result is not None:
            return

        while True:
            # first try SIGINT to allow stdout+stderr flushing
            self.log('Terminating (SIGINT)')
            os.kill(self.process_obj.pid, signal.SIGINT)
            self.killed = signal.SIGINT
            if self._poll_termination():
                break

            # SIGTERM maybe?
            self.log('Terminating (SIGTERM)')
            self.process_obj.terminate()
            self.killed = signal.SIGTERM
            if self._poll_termination():
                break

            # out of patience
            self.log('Terminating (SIGKILL)')
            self.process_obj.kill()
            self.killed = signal.SIGKILL
            break;

        self.process_obj.wait()
        self.cleanup()

    def cleanup(self):
        self.close_output_logs()
        if self.result == 0:
            self.log('Terminated: ok', rc=self.result)
        elif self.killed:
            self.log('Terminated', rc=self.result)
        else:
            self.err('Terminated: ERROR', rc=self.result)
            #self.err('stdout:\n', self.get_stdout_tail(prefix='| '), '\n')
            self.err('stderr:\n', self.get_stderr_tail(prefix='| '), '\n')

    def close_output_logs(self):
        self.dbg('Cleanup')
        for k, v in self.outputs.items():
            path, f = v
            if f:
                f.flush()
                f.close()
            self.outputs[k] = (path, None)

    def poll(self):
        if self.process_obj is None:
            return
        if self.result is not None:
            return
        self.result = self.process_obj.poll()
        if self.result is not None:
            self.cleanup()

    def get_output(self, which):
        v = self.outputs.get(which)
        if not v:
            return None
        path, f = v
        with open(path, 'r') as f2:
            return f2.read()

    def get_output_tail(self, which, tail=10, prefix=''):
        out = self.get_output(which).splitlines()
        tail = min(len(out), tail)
        return ('\n' + prefix).join(out[-tail:])

    def get_stdout(self):
        return self.get_output('stdout')

    def get_stderr(self):
        return self.get_output('stderr')

    def get_stdout_tail(self, tail=10, prefix=''):
        return self.get_output_tail('stdout', tail, prefix)

    def get_stderr_tail(self, tail=10, prefix=''):
        return self.get_output_tail('stderr', tail, prefix)

    def terminated(self):
        self.poll()
        return self.result is not None

    def wait(self):
        self.process_obj.wait()
        self.poll()


class RemoteProcess(Process):

    def __init__(self, remote_host, remote_cwd, *process_args, **process_kwargs):
        super().__init__(*process_args, **process_kwargs)
        self.remote_host = remote_host
        self.remote_cwd = remote_cwd

        # hacky: instead of just prepending ssh, i.e. piping stdout and stderr
        # over the ssh link, we should probably run on the remote side,
        # monitoring the process remotely.
        self.popen_args = ['ssh', '-t', self.remote_host,
                           'cd "%s"; %s' % (self.remote_cwd,
                                            ' '.join(['"%s"' % arg for arg in self.popen_args]))]
        self.dbg(self.popen_args, dir=self.run_dir, conf=self.popen_kwargs)

# vim: expandtab tabstop=4 shiftwidth=4