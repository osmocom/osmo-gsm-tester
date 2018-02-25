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
from .cdf import ease_in_out_duration, linear_with_duration
from osmo_gsm_tester import log

# System modules
import datetime
import subprocess
import signal
import tempfile
import os.path


def main():
    # Create a default log to stdout
    log.LogTarget().style(src=False)

    # We don't care what is happening to child processes we spawn!
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    loop = SimpleLoop()

    # TODO: Parse parameters and test composition. Right now we test
    # with a single set of values.
    num_ms = 10

    tmp_dir = tempfile.mkdtemp(suffix="osmo-ms-driver")
    log.log("Going to store files in ", tmp_dir=tmp_dir)

    # How long should starting all apps take
    time_start=datetime.timedelta(seconds=60)
    # In which steps to start processes
    time_step=datetime.timedelta(milliseconds=100)

    # Event server path
    event_server_path = os.path.join(tmp_dir,  "osmo_ms_driver.unix")

    # The function that decides when to start something
    cdf = ease_in_out_duration(time_start, time_step)

    # Event server to handle MS->test events
    ev_server = EventServer("ev_server", event_server_path)
    ev_server.listen(loop)
    #while True:
    #   loop.select()

    # Just a single test for now.
    test = MassUpdateLocationTest("lu_test", num_ms, cdf, ev_server, tmp_dir)

    # Run until everything has been launched
    test.launch(loop)

    # Wait for it to complete
    test.wait_for_result(loop)

    # Print stats
    test.print_stats()

if __name__ == '__main__':
    main()
