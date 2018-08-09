# osmo_gsm_tester: specifics pcu base abstract class
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

from abc import ABCMeta, abstractmethod
from . import log

class Pcu(log.Origin, metaclass=ABCMeta):
    """PCU Abstract Base Class."""

##############
# PROTECTED
##############

    def __init__(self, suite_run, bts, conf, name):
        """Base constructor. Must be called by subclass."""
        super().__init__(log.C_RUN, name)
        self.suite_run = suite_run
        self.bts = bts
        self.conf = conf

###################
# PUBLIC (test API included)
###################

    @abstractmethod
    def start(self, keepalive=False):
        """Start the PCU. Must be implemented by subclass."""
        pass

#------------------------------------------------------------------------------

class PcuDummy(Pcu):
    """PCU for BTS without proper PCU control"""

    def __init__(self, suite_run, bts, conf):
        super().__init__(suite_run, bts, conf, 'PcuDummy')

    def start(self, keepalive=False):
        pass

# vim: expandtab tabstop=4 shiftwidth=4
