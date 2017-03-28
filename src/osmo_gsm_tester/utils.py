# osmo_gsm_tester: language snippets
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
import fcntl

class listdict:
    'a dict of lists { "a": [1, 2, 3],  "b": [1, 2] }'
    def __getattr__(ld, name):
        if name == 'add':
            return ld.__getattribute__(name)
        return ld.__dict__.__getattribute__(name)

    def add(ld, name, item):
        l = ld.__dict__.get(name)
        if not l:
            l = []
            ld.__dict__[name] = l
        l.append(item)
        return l

    def add_dict(ld, d):
        for k,v in d.items():
            ld.add(k, v)

    def __setitem__(ld, name, val):
        return ld.__dict__.__setitem__(name, val)

    def __getitem__(ld, name):
        return ld.__dict__.__getitem__(name)

    def __str__(ld):
        return ld.__dict__.__str__()


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
        try:
            return dict2obj(getattr(self.obj, key))
        except AttributeError:
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)

class ListProxy:
    'allow nesting for DictProxy'
    def __init__(self, obj):
        self.obj = obj

    def __getitem__(self, key):
        return dict2obj(self.obj[key])

def dict2obj(value):
    if isinstance(value, dict):
        return DictProxy(value)
    if isinstance(value, (tuple, list)):
        return ListProxy(value)
    return value


class FileLock:
    def __init__(self, path, owner):
        self.path = path
        self.owner = owner
        self.f = None

    def __enter__(self):
        if self.f is not None:
            return
        self.fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
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


# vim: expandtab tabstop=4 shiftwidth=4
