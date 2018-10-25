# osmo_gsm_tester: process management
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import subprocess
import signal
from datetime import datetime

from . import log
from .event_loop import MainLoop
from .util import Dir

class Process(log.Origin):

    def __init__(self, name, run_dir, popen_args, **popen_kwargs):
        super().__init__(log.C_RUN, name)
        self.process_obj = None
        self.result = None
        self.killed = None
        self.name_str = name
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
        f.write('(launched: %s)\n' % datetime.now().strftime(log.LONG_DATEFMT))
        f.flush()
        self.outputs[name] = (path, f)
        return f

    def launch(self):
        log.dbg('cd %r; %s %s' % (
                os.path.abspath(str(self.run_dir)),
                ' '.join(['%s=%r'%(k,v) for k,v in self.popen_kwargs.get('env', {}).items()]),
                ' '.join(self.popen_args)))

        self.process_obj = subprocess.Popen(
            self.popen_args,
            stdout=self.make_output_log('stdout'),
            stderr=self.make_output_log('stderr'),
            stdin=subprocess.PIPE,
            shell=False,
            cwd=self.run_dir.path,
            **self.popen_kwargs)
        self.set_name(self.name_str, pid=self.process_obj.pid)
        self.log('Launched')

    def respawn(self):
        self.dbg('respawn')
        assert not self.is_running()
        self.result = None
        self.killed = None
        self.launch()

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
        self.dbg('Cleanup')
        self.close_output_logs()
        if self.result == 0:
            self.log('Terminated: ok', rc=self.result)
        elif self.killed:
            self.log('Terminated', rc=self.result)
        else:
            self.err('Terminated: ERROR', rc=self.result)
            #self.log_stdout_tail()
            self.log_stderr_tail()

    def log_stdout_tail(self):
        m = self.get_stdout_tail(prefix='| ')
        if not m:
            return
        self.log('stdout:\n', m, '\n')

    def log_stderr_tail(self):
        m = self.get_stderr_tail(prefix='| ')
        if not m:
            return
        self.log('stderr:\n', m, '\n')

    def close_output_logs(self):
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

    def is_running(self, poll_first=True):
        if poll_first:
            self.poll()
        return self.process_obj is not None and self.result is None

    def get_output(self, which):
        v = self.outputs.get(which)
        if not v:
            return None
        path, f = v
        with open(path, 'r') as f2:
            return f2.read()

    def get_output_tail(self, which, tail=10, prefix=''):
        out = self.get_output(which)
        if not out:
            return None
        out = out.splitlines()
        tail = min(len(out), tail)
        return prefix + ('\n' + prefix).join(out[-tail:])

    def get_stdout(self):
        return self.get_output('stdout')

    def get_stderr(self):
        return self.get_output('stderr')

    def get_stdout_tail(self, tail=10, prefix=''):
        return self.get_output_tail('stdout', tail, prefix)

    def get_stderr_tail(self, tail=10, prefix=''):
        return self.get_output_tail('stderr', tail, prefix)

    def terminated(self, poll_first=True):
        if poll_first:
            self.poll()
        return self.result is not None

    def wait(self, timeout=300):
        MainLoop.wait(self, self.terminated, timeout=timeout)


class RemoteProcess(Process):

    def __init__(self, name, run_dir, remote_user, remote_host, remote_cwd, popen_args, **popen_kwargs):
        super().__init__(name, run_dir, popen_args, **popen_kwargs)
        self.remote_user = remote_user
        self.remote_host = remote_host
        self.remote_cwd = remote_cwd

        # hacky: instead of just prepending ssh, i.e. piping stdout and stderr
        # over the ssh link, we should probably run on the remote side,
        # monitoring the process remotely.
        if self.remote_cwd:
            cd = 'cd "%s"; ' % self.remote_cwd
        else:
            cd = ''
        # We need double -t to force tty and be able to forward signals to
        # processes (SIGHUP) when we close ssh on the local side. As a result,
        # stderr seems to be merged into stdout in ssh client.
        self.popen_args = ['ssh', '-t', '-t', self.remote_user+'@'+self.remote_host,
                           '%s%s' % (cd,
                                     ' '.join(self.popen_args))]
        self.dbg(self.popen_args, dir=self.run_dir, conf=self.popen_kwargs)

def run_proc_sync(proc):
    try:
        proc.launch()
        proc.wait()
    except Exception as e:
        proc.terminate()
        raise e
    if proc.result != 0:
        log.ctx(proc)
        raise log.Error('Exited in error')

def run_local_sync(run_dir, name, popen_args):
    run_dir =run_dir.new_dir(name)
    proc = Process(name, run_dir, popen_args)
    run_proc_sync(proc)

def run_remote_sync(run_dir, remote_user, remote_addr, name, popen_args, remote_cwd=None):
    run_dir = run_dir.new_dir(name)
    proc = RemoteProcess(name, run_dir, remote_user, remote_addr, remote_cwd, popen_args)
    run_proc_sync(proc)

def scp(run_dir, remote_user, remote_addr, name, local_path, remote_path):
    run_local_sync(run_dir, name, ('scp', '-r', local_path, '%s@%s:%s' % (remote_user, remote_addr, remote_path)))

def copy_inst_ssh(run_dir, inst, remote_dir, remote_user, remote_addr, remote_rundir_append, cfg_file_name):
    remote_inst = Dir(remote_dir.child(os.path.basename(str(inst))))
    remote_dir_str = str(remote_dir)
    run_remote_sync(run_dir, remote_user, remote_addr, 'rm-remote-dir', ('test', '!', '-d', remote_dir_str, '||', 'rm', '-rf', remote_dir_str))
    run_remote_sync(run_dir, remote_user, remote_addr, 'mk-remote-dir', ('mkdir', '-p', remote_dir_str))
    scp(run_dir, remote_user, remote_addr, 'scp-inst-to-remote', str(inst), remote_dir_str)

    remote_run_dir = remote_dir.child(remote_rundir_append)
    run_remote_sync(run_dir, remote_user, remote_addr, 'mk-remote-run-dir', ('mkdir', '-p', remote_run_dir))

    remote_config_file = remote_dir.child(os.path.basename(cfg_file_name))
    scp(run_dir, remote_user, remote_addr, 'scp-cfg-to-remote', cfg_file_name, remote_config_file)
    return remote_inst

# vim: expandtab tabstop=4 shiftwidth=4
