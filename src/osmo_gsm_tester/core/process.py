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
from abc import ABCMeta, abstractmethod
from datetime import datetime
import re

from . import log
from .event_loop import MainLoop
from .util import Dir

class TerminationStrategy(log.Origin, metaclass=ABCMeta):
    """A baseclass for terminating a collection of processes."""

    def __init__(self):
        self._processes = []

    def add_process(self, process):
        """Remembers a process that needs to be terminated."""
        self._processes.append(process)

    @abstractmethod
    def terminate_all(self):
        "Terminates all scheduled processes and waits for the termination."""
        pass


class ParallelTerminationStrategy(TerminationStrategy):
    """Processes will be terminated in parallel."""

    def _prune_dead_processes(self, poll_first):
        """Removes all dead processes from the list."""
        # Remove all processes that terminated!
        self._processes = list(filter(lambda proc: proc.is_running(poll_first), self._processes))

    def _build_process_map(self):
        """Builds a mapping from pid to process."""
        self._process_map = {}
        for process in self._processes:
            pid = process.pid()
            if pid is None:
                continue
            self._process_map[pid] = process

    def _poll_once(self):
        """Polls for to be collected children once."""
        pid, result = os.waitpid(0, os.WNOHANG)
        # Did some other process die?
        if pid == 0:
            return False
        proc = self._process_map.get(pid)
        if proc is None:
            self.dbg("Unknown process with pid(%d) died." % pid)
            return False
        # Update the process state and forget about it
        self.log("PID %d died..." % pid)
        proc.result = result
        proc.cleanup()
        self._processes.remove(proc)
        del self._process_map[pid]
        return True

    def _poll_for_termination(self, time_to_wait_for_term=5):
        """Waits for the termination of processes until timeout|all ended."""

        wait_step = 0.001
        waited_time = 0
        while len(self._processes) > 0:
            # Collect processes until there are none to be collected.
            while True:
                try:
                    if not self._poll_once():
                        break
                except ChildProcessError:
                    break

            # All processes died and we can return before sleeping
            if len(self._processes) == 0:
                break
            waited_time += wait_step
            # make wait_step approach 1.0
            wait_step = (1. + 5. * wait_step) / 6.
            if waited_time >= time_to_wait_for_term:
                break
            time.sleep(wait_step)

    def terminate_all(self):
        num_processes = len(self._processes)
        self.dbg("Scheduled to terminate %d processes." % num_processes)
        if num_processes == 0:
            return
        self._prune_dead_processes(True)
        self._build_process_map()

        # Iterate through all signals.
        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGKILL]:
            self.dbg("Starting to kill with %s" % sig.name)
            for process in self._processes:
                process.kill(sig)
            if sig == signal.SIGKILL:
                continue
            self._poll_for_termination()
            if len(self._processes) == 0:
                return


class Process(log.Origin):

    DEFAULT_WAIT_TIMEOUT = 300 # seconds

    def __init__(self, name, run_dir, popen_args, **popen_kwargs):
        super().__init__(log.C_RUN, name)
        self.process_obj = None
        self.result = None
        self.killed = None
        self.default_wait_timeout = Process.DEFAULT_WAIT_TIMEOUT
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

    def set_default_wait_timeout(self, timeout):
        assert timeout
        self.default_wait_timeout = timeout

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

    def get_counter_stdout(self, keyword):
        # Match stdout against keyword
        n = 0
        stdout_lines = (self.get_stdout() or '').splitlines()
        for l in stdout_lines:
            if keyword in l:
                n += 1
        return n

    def launch(self):
        preexec_fn = None
        log.dbg('cd %r; %s %s' % (
                os.path.abspath(str(self.run_dir)),
                ' '.join(['%s=%r'%(k,v) for k,v in self.popen_kwargs.get('env', {}).items()]),
                ' '.join(self.popen_args)))

        if self.popen_args[0] == "sudo":
            # sudo drops forwarding of signals sent by processes of the same
            # process group, which means by default will drop signals from
            # parent and children processes. By moving it to another group, we
            # will later be able to kill it.
            # Note: sudo documentation is wrong, since it states it only drops
            # signals from children.
            preexec_fn = os.setpgrp

        self.process_obj = subprocess.Popen(
            self.popen_args,
            stdout=self.make_output_log('stdout'),
            stderr=self.make_output_log('stderr'),
            stdin=subprocess.PIPE,
            preexec_fn=preexec_fn,
            shell=False,
            cwd=self.run_dir.path,
            **self.popen_kwargs)
        self.set_name(self.name_str, pid=self.process_obj.pid)
        self.log('Launched')

    def launch_sync(self, raise_nonsuccess=True):
        '''
        calls launch() method and block waiting for it to finish, serving the
        mainloop meanwhile.
        '''
        try:
            self.launch()
            self.wait()
        except Exception as e:
            self.terminate()
            raise e
        if raise_nonsuccess and self.result != 0:
            raise self.RunError('launch_sync()')
        return self.result

    def respawn(self):
        self.dbg('respawn')
        assert not self.is_running()
        self.result = None
        self.killed = None
        return self.launch()

    def respawn_sync(self, raise_nonsuccess=True):
        self.dbg('respawn_sync')
        assert not self.is_running()
        self.result = None
        self.killed = None
        return self.launch_sync(raise_nonsuccess)

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

    def send_signal(self, sig):
        os.kill(self.process_obj.pid, sig)

    def pid(self):
        if self.process_obj is None:
            return None
        return self.process_obj.pid

    def kill(self, sig):
        """Kills the process with the given signal and remembers it."""
        self.log('Terminating (%s)' % sig.name)
        self.send_signal(sig)
        self.killed = sig

    def terminate(self):
        if self.process_obj is None:
            return
        if self.result is not None:
            return

        while True:
            # first try SIGINT to allow stdout+stderr flushing
            self.kill(signal.SIGINT)
            if self._poll_termination():
                break

            # SIGTERM maybe?
            self.kill(signal.SIGTERM)
            if self._poll_termination():
                break

            # out of patience
            self.kill(signal.SIGKILL)
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
            self.log_stdout_tail()
            self.log_stderr_tail()

    def log_stdout_tail(self):
        m = self.get_stdout_tail(prefix='| ')
        if not m:
            return
        self.log('stdout:', '\n' + m, '\n')

    def log_stderr_tail(self):
        m = self.get_stderr_tail(prefix='| ')
        if not m:
            return
        self.log('stderr:', '\n' + m, '\n')

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

    @staticmethod
    def end_ansi_colors(txt):
        '''Make sure no ANSI colors leak out of logging output'''
        color_off = '\033[0;m'
        color_any = '\033['
        if txt.rfind(color_any) > txt.rfind(color_off):
            return txt + color_off
        return txt

    def get_output(self, which, since_mark=0):
        ''' Read process output. For since_mark, see get_output_mark(). '''
        path = self.get_output_file(which)
        if path is None:
            return None
        with open(path, 'r') as f:
            if since_mark > 0:
                f.seek(since_mark)
            return self.end_ansi_colors(f.read())

    def get_output_file(self, which):
        ''' Return filename for given output '''
        v = self.outputs.get(which)
        if not v:
            return None
        path, f = v
        return path

    def get_output_tail(self, which, tail=10, prefix=''):
        out = self.get_output(which)
        if not out:
            return None
        out = out.splitlines()
        tail = min(len(out), tail)
        return prefix + self.end_ansi_colors(('\n' + prefix).join(out[-tail:]))

    def get_output_mark(self, which):
        '''Usage:
             # remember a start marker
             my_mark = my_process.get_output_mark('stderr')

             do_actions_that_produce_log_output()

             my_log = my_process.get_output('stderr', since_mark=my_mark)
             # my_log contains the stderr of that process since the start marker.
        '''
        path = self.get_output_file(which)
        if path is None:
            return None
        with open(path, 'r') as f:
            return f.seek(0, 2)

    def grep_output(self, which, regex, since_mark=0, line_nrs=False):
        lines = self.get_output(which, since_mark=since_mark).splitlines()
        if not lines:
            return None
        matches = []
        r = re.compile(regex)
        line_nr = since_mark
        for line in lines:
            line_nr += 1
            if r.search(line):
                line = self.end_ansi_colors(line)
                if line_nrs:
                    matches.append((line_nr, line))
                else:
                    matches.append(line)
        return matches

    def get_stdout(self, since_mark=0):
        return self.get_output('stdout', since_mark=since_mark)

    def get_stderr(self, since_mark=0):
        return self.get_output('stderr', since_mark=since_mark)

    def get_stdout_tail(self, tail=10, prefix=''):
        return self.get_output_tail('stdout', tail, prefix)

    def get_stderr_tail(self, tail=10, prefix=''):
        return self.get_output_tail('stderr', tail, prefix)

    def terminated(self, poll_first=True):
        if poll_first:
            self.poll()
        return self.result is not None

    def wait(self, timeout=None):
        if timeout is None:
            timeout = self.default_wait_timeout
        MainLoop.wait(self.terminated, timeout=timeout)

    def stdin_write(self, cmd):
        '''
        Send a cmd to the stdin of a process (convert to byte before)
        '''
        if self.process_obj.stdin is not None:
            self.process_obj.stdin.write(cmd.encode("utf-8"))
            self.process_obj.stdin.flush()

    def RunError(self, msg_prefix):
        'Get a log.Error filled in with Result information. Use when program is terminated and result !=0'
        msg = '%s: local process exited with status %d' % (msg_prefix, self.result)
        return log.Error(msg)

class RemoteProcess(Process):

    def __init__(self, name, run_dir, remote_user, remote_host, remote_cwd, popen_args,
                 remote_env={}, remote_port=None, **popen_kwargs):
        super().__init__(name, run_dir, popen_args, **popen_kwargs)
        self.remote_user = remote_user
        self.remote_host = remote_host
        self.remote_cwd = remote_cwd
        self.remote_env = remote_env
        self.remote_port = remote_port

        # hacky: instead of just prepending ssh, i.e. piping stdout and stderr
        # over the ssh link, we should probably run on the remote side,
        # monitoring the process remotely.
        if self.remote_cwd:
            cd = 'cd "%s";' % self.remote_cwd
        else:
            cd = ''
        # We need double -t to force tty and be able to forward signals to
        # processes (SIGHUP) when we close ssh on the local side. As a result,
        # stderr seems to be merged into stdout in ssh client.
        self.popen_args = ['ssh', '-t', '-t', self.remote_user+'@'+self.remote_host,
                           '%s %s %s' % (cd,
                                         ' '.join(['%s=%r'%(k,v) for k,v in self.remote_env.items()]),
                                         ' '.join(self.popen_args))]
        if self.remote_port:
            self.popen_args.insert(1, '-p')
            self.popen_args.insert(2, self.remote_port)

        self.dbg(self.popen_args, dir=self.run_dir, conf=self.popen_kwargs, remote_env=self.remote_env)

    def RunError(self, msg_prefix):
        'Overwrite Process method with ssh extra information'
        # man ssh states it returns 255 if an ssh error occurred:
        msg = msg_prefix + ': '
        if self.result == 255:
            tail = ' (' + (self.get_stderr_tail(tail=1, prefix='') or '').rstrip() + ')'
            msg += 'local ssh process exited with status %d%s' % (self.result, tail if 'ssh' in tail else '')
        else:
            msg += 'remote process exited with status %d' % (self.result)
        return log.Error(msg)

class NetNSProcess(Process):
    NETNS_EXEC_BIN = 'osmo-gsm-tester_netns_exec.sh'
    def __init__(self, name, run_dir, netns, popen_args, **popen_kwargs):
        super().__init__(name, run_dir, popen_args, **popen_kwargs)
        self.netns = netns

        self.popen_args = ['sudo', self.NETNS_EXEC_BIN, self.netns] + list(popen_args)
        self.dbg(self.popen_args, dir=self.run_dir, conf=self.popen_kwargs)

    # HACK: Since we run under sudo, only way to kill root-owned process is to kill as root...
    # This function is overwritten from Process.
    def send_signal(self, sig):
        if sig == signal.SIGKILL:
            # if we kill sudo, its children (bash running NETNS_EXEC_BIN +
            # tcpdump under it) are kept alive. Let's instead tell the script to
            # kill tcpdump:
            sig = signal.SIGUSR1
        kill_cmd = ('kill', '-%d' % int(sig), str(self.process_obj.pid))
        run_local_netns_sync(self.run_dir, self.name()+"-kill"+str(sig), self.netns, kill_cmd)

class RemoteNetNSProcess(RemoteProcess):
    NETNS_EXEC_BIN = 'osmo-gsm-tester_netns_exec.sh'
    def __init__(self, name, run_dir, remote_user, remote_host, remote_cwd, netns, popen_args, **popen_kwargs):
        self.netns = netns
        args = ['sudo', self.NETNS_EXEC_BIN, self.netns] + list(popen_args)
        super().__init__(name, run_dir, remote_user, remote_host, remote_cwd, args, **popen_kwargs)

class AdbProcess(Process):
    def __init__(self, name, run_dir, adb_serial, popen_args, **popen_kwargs):
        super().__init__(name, run_dir, popen_args, **popen_kwargs)
        self.adb_serial = adb_serial

        self.popen_args = ['adb', '-s', self.adb_serial, 'exec-out', 'su', '-c'] + list(popen_args)
        self.dbg(self.popen_args, dir=self.run_dir, conf=self.popen_kwargs)

def run_local_sync(run_dir, name, popen_args):
    run_dir =run_dir.new_dir(name)
    proc = Process(name, run_dir, popen_args)
    proc.launch_sync()
    return proc

def run_local_netns_sync(run_dir, name, netns, popen_args):
    run_dir =run_dir.new_dir(name)
    proc = NetNSProcess(name, run_dir, netns, popen_args)
    proc.launch_sync()
    return proc
# vim: expandtab tabstop=4 shiftwidth=4
