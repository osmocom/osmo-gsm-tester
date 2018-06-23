# osmo_ms_driver: Main test runner
#
# Copyright (C) 2018 by Holger Hans Peter Freyther
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

# Local modules
from .event_server import EventServer
from .simple_loop import SimpleLoop
from .location_update_test import MassUpdateLocationTest
from .cdf import cdfs
from osmo_gsm_tester import log

# System modules
import argparse
import atexit
import datetime
import signal
import tempfile
import os.path
import os

def parser():
    parser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--launch-duration', dest='launch_duration',
            default=60, type=int,
            help="Time launching applications should take in seconds")
    parser.add_argument('-i', '--launch-interval', dest='launch_interval',
            default=100, type=int,
            help="Time between launching in milliseconds")
    parser.add_argument('-d', '--distribution', dest="cdf_name",
            choices=cdfs.keys(), default="ease_in_out",
            help="Curve to use for starting within launch duration")
    parser.add_argument('-m', '--number-ms', dest="num_ms",
            default=10, type=int,
            help="Number of MobileStations to simulate")
    return parser

def main():
    # Create a default log to stdout
    log.LogTarget().style(src=False)

    args = parser().parse_args()

    # We don't care what is happening to child processes we spawn!
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    loop = SimpleLoop()

    tmp_dir = tempfile.mkdtemp(suffix="osmo-ms-driver")
    log.log("Going to store files in ", tmp_dir=tmp_dir)

    # How long should starting all apps take
    time_start=datetime.timedelta(seconds=args.launch_duration)
    # In which steps to start processes
    time_step=datetime.timedelta(milliseconds=args.launch_interval)

    # Event server path
    event_server_path = os.path.join(tmp_dir,  "osmo_ms_driver.unix")

    # The function that decides when to start something
    cdf = cdfs[args.cdf_name](time_start, time_step)

    # Event server to handle MS->test events
    ev_server = EventServer("ev_server", event_server_path)
    ev_server.listen(loop)

    # Just a single test for now.
    test = MassUpdateLocationTest("lu_test", args.num_ms, cdf, ev_server, tmp_dir)
    atexit.register(test.stop_all)

    # Run until everything has been launched
    test.run_test(loop)

    # Print stats
    test.print_stats()

if __name__ == '__main__':
    main()
