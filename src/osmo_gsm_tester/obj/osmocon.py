# osmo_gsm_tester: specifics for running an osmocon
#
# Copyright (C) 2018 by sysmocom - s.f.m.c. GmbH
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

import os
import tempfile

from ..core import log, util, process
from ..core import schema
from ..core.event_loop import MainLoop

def on_register_schemas():
    resource_schema = {
        'serial_device': schema.STR,
        }
    schema.register_resource_schema('osmocon_phone', resource_schema)


class Osmocon(log.Origin):

    FIRMWARE_FILE="opt/osmocom-bb/target/firmware/board/compal_e88/layer1.compalram.bin"

    def __init__(self, testenv, conf):
        serial_device = conf.get('serial_device')
        if serial_device is None:
            raise log.Error('osmocon_phone contains no attr "serial_device"')
        self.serial_device = os.path.realpath(serial_device)
        super().__init__(log.C_RUN, 'osmocon_%s' % os.path.basename(self.serial_device))
        self.run_dir = None
        self.process = None
        self.testenv = testenv
        self.conf = conf
        self.sk_tmp_dir = tempfile.mkdtemp('', 'ogtosmoconsk')
        if len(self.l2_socket_path().encode()) > 107:
            raise log.Error('Path for l2 socket is longer than max allowed len for unix socket path (107):', self.l2_socket_path())
        if len(self.loader_socket_path().encode()) > 107:
            raise log.Error('Path for loader socket is longer than max allowed len for unix socket path (107):', self.loader_socket_path())

    def l2_socket_path(self):
        return os.path.join(self.sk_tmp_dir, 'osmocom_l2')

    def loader_socket_path(self):
        return os.path.join(self.sk_tmp_dir, 'osmocom_loader')

    def start(self):
        self.log('Resetting the phone')
        # TODO: make sure the pone is powered off before starting osmocon

        self.log('Starting osmocon')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))

        inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmocom-bb')))

        binary = inst.child('sbin', 'osmocon')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        firmware_path = os.path.join(str(inst), Osmocon.FIRMWARE_FILE)
        if not os.path.isfile(firmware_path):
            raise RuntimeError('Binary missing: %r' % firmware_path)
        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary, '-p', self.serial_device,
                                       '-m', 'c123xor',
                                       '-s', self.l2_socket_path(),
                                       '-l', self.loader_socket_path(),
                                        firmware_path),
                                       env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()
        self.log('Waiting for osmocon to be up and running')
        MainLoop.wait(os.path.exists, self.l2_socket_path())

    def running(self):
        return not self.process.terminated()

    def cleanup(self):
        if self.sk_tmp_dir:
            try:
                os.remove(self.l2_socket_path())
            except OSError:
                pass
            try:
                os.remove(self.loader_socket_path())
            except OSError:
                pass
            os.rmdir(self.sk_tmp_dir)

# vim: expandtab tabstop=4 shiftwidth=4
