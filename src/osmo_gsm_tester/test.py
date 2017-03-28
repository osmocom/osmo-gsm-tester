# osmo_gsm_tester: prepare a test run and provide test API
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

import sys, os
import pprint
import inspect

from . import suite as _suite
from . import log
from . import resource

# load the configuration for the test
suite = _suite.Suite(sys.path[0])
test = _suite.Test(suite, os.path.basename(inspect.stack()[-1][1]))

def test_except_hook(*exc_info):
    log.exn_add_info(exc_info, test)
    log.exn_add_info(exc_info, suite)
    log.log_exn(exc_info=exc_info)

sys.excepthook = test_except_hook

orig_stdout, sys.stdout = sys.stdout, test

resources = {}
	
# vim: expandtab tabstop=4 shiftwidth=4
