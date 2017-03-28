# osmo_gsm_tester: manage resources
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

from . import log
from . import config
from .utils import listdict, FileLock

class Resources(log.Origin):

    def __init__(self, config_path, lock_dir):
        self.config_path = config_path
        self.lock_dir = lock_dir
        self.set_name(conf=self.config_path, lock=self.lock_dir)

    def ensure_lock_dir_exists(self):
        if not os.path.isdir(self.lock_dir):
            os.makedirs(self.lock_dir)


global_resources = listdict()

def register(kind, instance):
    global global_resources
    global_resources.add(kind, instance)

def reserve(user, config):
    asdf

def read_conf(path):
    with open(path, 'r') as f:
        conf = f.read()

# vim: expandtab tabstop=4 shiftwidth=4
