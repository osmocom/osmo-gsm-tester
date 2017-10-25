# osmo_gsm_tester: language snippets
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
import sys
import time
import fcntl
import hashlib
import tempfile
import shutil
import atexit
import threading
import importlib.util
import fcntl
import tty
import readline
import subprocess

def prepend_library_path(path):
    lp = os.getenv('LD_LIBRARY_PATH')
    if not lp:
        return path
    return path + ':' + lp

def change_elf_rpath(binary, paths, run_dir):
    '''
    Change RPATH field in ELF executable binary.
    This feature can be used to tell the loaded to load the trial libraries, as
    LD_LIBRARY_PATH is disabled for paths with modified capabilities.
    '''
    from .process import Process
    proc = Process('patchelf', run_dir, ['patchelf', '--set-rpath', paths, binary])
    proc.launch()
    proc.wait()
    if proc.result != 0:
        raise RuntimeError('patchelf finished with err code %d' % proc.result)

def ip_to_iface(ip):
    try:
        for iface in os.listdir('/sys/class/net'):
            proc = subprocess.Popen(['ip', 'addr', 'show', 'dev', iface], stdout=subprocess.PIPE, universal_newlines=True)
            for line in proc.stdout.readlines():
                if 'inet' in line and ' ' + ip + '/' in line:
                    return line.split()[-1]
    except Exception as e:
        pass
    return None

def setcap_net_raw(binary, run_dir):
    '''
    This functionality requires specific setup on the host running
    osmo-gsm-tester. See osmo-gsm-tester manual for more information.
    '''
    from .process import Process
    SETCAP_NET_BIN = 'osmo-gsm-tester_setcap_net_raw.sh'
    proc = Process(SETCAP_NET_BIN, run_dir, ['sudo', 'osmo-gsm-tester_setcap_net_raw.sh', binary])
    proc.launch()
    proc.wait()
    if proc.result != 0:
        raise RuntimeError('%s finished with err code %d' % (SETCAP_NET_BIN, proc.result))

class listdict(dict):
    'a dict of lists { "a": [1, 2, 3],  "b": [1, 2] }'

    def add(self, name, item):
        l = self.get(name)
        if not l:
            l = []
            self[name] = l
        l.append(item)
        return l

    def add_dict(self, d):
        for k,v in d.items():
            self.add(k, v)

class DictProxy:
    '''
    allow accessing dict entries like object members
    syntactical sugar, adapted from http://stackoverflow.com/a/31569634
    so that e.g. templates can do ${bts.member} instead of ${bts['member']}
    '''
    def __init__(self, obj):
        self.obj = obj

    def __getitem__(self, key):
        return dict2obj(self.obj[key])

    def __getattr__(self, key):
        'provide error information to know which template item was missing'
        try:
            return dict2obj(getattr(self.obj, key))
        except AttributeError:
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)

def dict2obj(value):
    if is_list(value) or is_dict(value):
        return DictProxy(value)
    return value


class FileLock:
    def __init__(self, path, owner):
        self.path = path
        self.owner = owner
        self.f = None

    def __enter__(self):
        if self.f is not None:
            return
        self.fd = os.open(self.path, os.O_CREAT | os.O_WRONLY)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        os.truncate(self.fd, 0)
        os.write(self.fd, str(self.owner).encode('utf-8'))
        os.fsync(self.fd)

    def __exit__(self, *exc_info):
        #fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.truncate(self.fd, 0)
        os.fsync(self.fd)
        os.close(self.fd)
        self.fd = -1

    def lock(self):
        self.__enter__()

    def unlock(self):
        self.__exit__()


class Dir():
    LOCK_FILE = 'lock'

    def __init__(self, path):
        self.path = path
        self.lock_path = os.path.join(self.path, Dir.LOCK_FILE)

    def lock(self, origin_id):
        '''
        return lock context, usage:

          with my_dir.lock(origin):
              read_from(my_dir.child('foo.txt'))
              write_to(my_dir.child('bar.txt'))
        '''
        self.mkdir()
        return FileLock(self.lock_path, origin_id)

    @staticmethod
    def ensure_abs_dir_exists(*path_elements):
        l = len(path_elements)
        if l < 1:
            raise RuntimeError('Cannot create empty path')
        if l == 1:
            path = path_elements[0]
        else:
            path = os.path.join(*path_elements)
        if not os.path.isdir(path):
            os.makedirs(path)

    def child(self, *rel_path):
        if not rel_path:
            return self.path
        return os.path.join(self.path, *rel_path)

    def mk_parentdir(self, *rel_path):
        child = self.child(*rel_path)
        child_parent = os.path.dirname(child)
        Dir.ensure_abs_dir_exists(child_parent)
        return child

    def mkdir(self, *rel_path):
        child = self.child(*rel_path)
        Dir.ensure_abs_dir_exists(child)
        return child

    def children(self):
        return os.listdir(self.path)

    def exists(self, *rel_path):
        return os.path.exists(self.child(*rel_path))

    def isdir(self, *rel_path):
        return os.path.isdir(self.child(*rel_path))

    def isfile(self, *rel_path):
        return os.path.isfile(self.child(*rel_path))

    def new_child(self, *rel_path):
        attempt = 1
        prefix, suffix = os.path.splitext(self.child(*rel_path))
        rel_path_fmt = '%s%%s%s' % (prefix, suffix)
        while True:
            path = rel_path_fmt % (('_%d'%attempt) if attempt > 1 else '')
            if not os.path.exists(path):
                break
            attempt += 1
            continue
        Dir.ensure_abs_dir_exists(os.path.dirname(path))
        return path

    def rel_path(self, path):
        return os.path.relpath(path, self.path)

    def touch(self, *rel_path):
        touch_file(self.child(*rel_path))

    def new_file(self, *rel_path):
        path = self.new_child(*rel_path)
        touch_file(path)
        return path

    def new_dir(self, *rel_path):
        path = self.new_child(*rel_path)
        Dir.ensure_abs_dir_exists(path)
        return path

    def __str__(self):
        return self.path
    def __repr__(self):
        return self.path

def touch_file(path):
    with open(path, 'a') as f:
        f.close()

def is_dict(l):
    return isinstance(l, dict)

def is_list(l):
    return isinstance(l, (list, tuple))


def dict_add(a, *b, **c):
    for bb in b:
        a.update(bb)
    a.update(c)
    return a

def _hash_recurse(acc, obj, ignore_keys):
    if is_dict(obj):
        for key, val in sorted(obj.items()):
            if key in ignore_keys:
                continue
            _hash_recurse(acc, val, ignore_keys)
        return

    if is_list(obj):
        for item in obj:
            _hash_recurse(acc, item, ignore_keys)
        return

    acc.update(str(obj).encode('utf-8'))

def hash_obj(obj, *ignore_keys):
    acc = hashlib.sha1()
    _hash_recurse(acc, obj, ignore_keys)
    return acc.hexdigest()


def md5(of_content):
    if isinstance(of_content, str):
        of_content = of_content.encode('utf-8')
    return hashlib.md5(of_content).hexdigest()

def md5_of_file(path):
    with open(path, 'rb') as f:
        return md5(f.read())

_tempdir = None

def get_tempdir(remove_on_exit=True):
    global _tempdir
    if _tempdir is not None:
        return _tempdir
    _tempdir = tempfile.mkdtemp()
    if remove_on_exit:
        atexit.register(lambda: shutil.rmtree(_tempdir))
    return _tempdir


if hasattr(importlib.util, 'module_from_spec'):
    def run_python_file(module_name, path):
        spec = importlib.util.spec_from_file_location(module_name, path)
        spec.loader.exec_module( importlib.util.module_from_spec(spec) )
else:
    from importlib.machinery import SourceFileLoader
    def run_python_file(module_name, path):
        SourceFileLoader(module_name, path).load_module()

def msisdn_inc(msisdn_str):
    'add 1 and preserve leading zeros'
    return ('%%0%dd' % len(msisdn_str)) % (int(msisdn_str) + 1)

class InputThread(threading.Thread):
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self.result = None

    def run(self):
        self.result = input(self.prompt)

def input_polling(prompt, poll_func):
    input_thread = InputThread(prompt)
    input_thread.start()

    while input_thread.is_alive():
        poll_func()
        time.sleep(1)

    input_thread.join()
    return input_thread.result

def str2bool(val):
    if val is None or not val:
        return False
    if val.upper() in ['FALSE', 'NO', 'OFF']:
        return False
    if val.upper() in ['TRUE','YES', 'ON']:
        return True
    raise ValueError('Invalid BOOL field: %r' % val)

def list_validate_same_elem_type(li):
    '''
    Checks that all elements in the list are of the same type and returns that type.
    If the list is empty, returns None
    If one of the elements is not of the same type, it throws a ValueError exception.
    '''
    if len(li) == 0:
        return None
    t = type(li[0])
    for elem in li:
        if type(elem) != t:
            raise ValueError('List contains elements of different types: %r vs %r' % (t, type(elem)))
    return t

def empty_instance_type(t):
    if t == dict:
        return {}
    elif t == list:
        return []
    elif t == tuple:
        return ()
    raise ValueError('type %r not supported!' % t)

def encryption2osmovty(val):
    assert val[:3] == 'a5_'
    return 'a5 ' + val[3:]

# vim: expandtab tabstop=4 shiftwidth=4
