# osmo_gsm_tester: class defining a Power Supply object
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

import sispm
from usb.core import USBError

from . import log, event_loop
from .powersupply import PowerSupply

class PowerSupplySispm(PowerSupply):
    """PowerSupply implementation using pysispm.

    The device object from sismpm is not cached into an attribute of the class
    instance because it is actually a libusb object keeping the device assigned
    to it until it destroyed, meaning it will block other users to use the whole
    device until the object is released. Instead, we pick the object in the
    smallest scope possible, and we re-try if we receive a "Resource Busy" error
    because we know it will be available in short time.
    """

    def _retry_usberr(self, func, *args):
        """Run function until it runs successfully, retry on spurious errors.

        Sometimes when operating the usb device, libusb reports the following spurious exception:
        [Errno 16] Resource busy -> This can appear if another instance is using the device.
        [Errno 110] Operation timed out

        Retrying after that it's usually enough.
        """
        while True:
            try:
                ret = func(*args)
                return ret
            except USBError as e:
                    if e.errno == 16 or e.errno==110:
                        self.log('skip usb error, retry', repr(e))
                        event_loop.sleep(self, 0.1)
                        continue
                    raise e

    def _get_device(self):
        """Get the sispm device object.

        It should be kept alive as short as possible as it blocks other users
        from using the device until the object is released.
        """
        mydevid = self.conf.get('device')
        devices = self._retry_usberr(sispm.connect)
        for d in devices:
            did = self._retry_usberr(sispm.getid, d)
            self.dbg('detected device:', did)
            if did == mydevid:
                self.dbg('found matching device: %s' % did)
                return d
        return None


########################
# PUBLIC - INTERNAL API
########################
    def __init__(self, conf):
        super().__init__(conf, 'sispm')
        mydevid = conf.get('device')
        if mydevid is None:
            raise log.Error('No "device" attribute provided in supply conf!')
        self.set_name('sispm-'+mydevid)
        myport = conf.get('port')
        if myport is None:
            raise log.Error('No "port" attribute provided in power_supply conf!')
        if not int(myport):
            raise log.Error('Wrong non numeric "port" attribute provided in power_supply conf!')
        self.port = int(myport)
        device = self._get_device()
        if device is None:
            raise log.Error('device with with id %s not found!' % mydevid)
        dmin = self._retry_usberr(sispm.getminport, device)
        dmax = self._retry_usberr(sispm.getmaxport, device)
        if dmin > self.port or dmax < self.port:
            raise log.Error('Out of range "port" attribute provided in power_supply conf!')

    def is_powered(self):
        """Get whether the device is powered on or off."""
        return self._retry_usberr(sispm.getstatus, self._get_device(), self.port)

    def power_set(self, onoff):
        """Turn on (onoff=True) or off (onoff=False) the device."""
        if onoff:
            self.dbg('switchon')
            self._retry_usberr(sispm.switchon, self._get_device(), self.port)
        else:
            self.dbg('switchoff')
            self._retry_usberr(sispm.switchoff, self._get_device(), self.port)


# vim: expandtab tabstop=4 shiftwidth=4
