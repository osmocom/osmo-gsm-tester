#!/usr/bin/env python3

# osmo_gsm_tester: invoke a single test run
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

'''osmo_gsm_tester: invoke a single test run.

./run_once.py ~/path/to/test_package/

Upon launch, a 'test_package/run-<date>' directory will be created.
When complete, a symbolic link 'test_package/last_run' will point at this dir.
The run dir then contains logs and test results.
'''

import osmo_gsm_tester

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-V', '--version', action='store_true',
            help='Show version')
    parser.add_argument('test_package', nargs='*',
            help='Directory containing binaries to test')
    args = parser.parse_args()

    if args.version:
        print(osmo_gsm_tester.__version__)
        exit(0)


# vim: expandtab tabstop=4 shiftwidth=4
