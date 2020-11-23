# osmo_gsm_tester: Base class for AndroidUE modems
#
# Copyright (C) 2020 by Software Radio Systems Limited
#
# Author: Nils Fürste <nils.fuerste@softwareradiosystems.com>
# Author: Bedran Karakoc <bedran.karakoc@softwareradiosystems.com>
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

from ..core import log, process
from abc import ABCMeta


class AndroidHost(log.Origin, metaclass=ABCMeta):
    """Base for everything AndroidUE related."""

##############
# PROTECTED
##############
    def __init__(self, name):
        log.Origin.__init__(self, log.C_TST, name)

########################
# PUBLIC - INTERNAL API
########################
    def run_androidue_cmd(self, name, popen_args):
        # This function executes the given command directly on the Android UE. Therefore,
        # ADB is used to execute commands locally and ssh for remote execution. Make sure
        # Android SDK Platform-Tools >= 23 is installed
        if self._run_node.is_local():
            # use adb instead of ssh
            run_dir = self.run_dir.new_dir(name)
            proc = process.AdbProcess(name, run_dir, self._run_node.adb_serial_id(), popen_args, env={})
        else:
            proc = self.rem_host.RemoteProcess(name, popen_args, remote_env={})
        return proc
