# osmo_gsm_tester: run_node: object holding information on a target env to run stuff.
#
# Copyright (C) 2020 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
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

from .core import log

class RunNode(log.Origin):

    T_LOCAL = 'local'
    T_REM_SSH = 'ssh'

    def __init__(self, type=None, run_addr=None, ssh_user=None, ssh_addr=None):
        super().__init__(log.C_RUN, 'runnode')
        self._type = type
        self._run_addr = run_addr
        self._ssh_user = ssh_user
        self._ssh_addr = ssh_addr
        if not self._type:
            raise log.Error('run_type not set')
        if not self._run_addr:
            raise log.Error('run_addr not set')
        if self._type == RunNode.T_LOCAL and (self._ssh_user or self._ssh_addr):
            raise log.Error('run_type=%s but ssh info set' % RunNode.T_LOCAL)
        if self._type == RunNode.T_REM_SSH and not (self._ssh_user and self._ssh_addr):
            raise log.Error('run_type=%s but ssh info NOT set' % RunNode.T_LOCAL)

        if self._type == RunNode.T_LOCAL:
            self.set_name('run-' + self._run_addr)
        else:
            self.set_name('run-' + self._run_addr + "(" + self._ssh_user + '@' + self._ssh_addr + ")")

    @classmethod
    def from_conf(cls, conf):
        return cls(conf.get('run_type', None), conf.get('run_addr', None), conf.get('ssh_user', None), conf.get('ssh_addr', None))

    def is_local(self):
        return self._type == RunNode.T_LOCAL

    def __str__(self):
        return self.name()

    def run_type(self):
        return self._type

    def run_addr(self):
        return self._run_addr

    def ssh_user(self):
        return self._ssh_user

    def ssh_addr(self):
        return self._ssh_addr

# vim: expandtab tabstop=4 shiftwidth=4
