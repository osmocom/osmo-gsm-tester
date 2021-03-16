# osmo_gsm_tester: common methods shared among srsLTE components
#
# Copyright (C) 2020 by Software Radio Systems Ltd
#
# Author: Andre Puschmann <andre@softwareradiosystems.com>
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

from ..core import log
from ..core.event_loop import MainLoop

class srslte_common(): # don't inherit from log.Origin here but instead use .name() from whoever inherits from us

    def __init__(self):
        self.log_file = None
        self.process = None
        self.metrics_file = None
        self.stop_sleep_time = 6 # We require at most 5s to stop
        self.log_kpi = None
        self.stdout_kpi = None
        self.csv_kpi = None

    def sleep_after_stop(self):
        # Only sleep once
        if self.stop_sleep_time > 0:
            MainLoop.sleep(self.stop_sleep_time)
            self.stop_sleep_time = 0

    def stop(self):
        # Send q+Enter to stdin to self-terminate application
        self.process.stdin_write('q\n')
        self.testenv.stop_process(self.process)
        self.sleep_after_stop()

    def get_kpis(self):
        ''' Merge all KPI and return as flat dict '''
        self.extract_kpis()
        kpi_flat = {}
        kpi_flat.update(self.log_kpi)
        kpi_flat.update(self.stdout_kpi)
        kpi_flat.update(self.csv_kpi)
        return kpi_flat

    def get_kpi_tree(self):
        ''' Return all KPI as dict of dict in which the source (e.g. stdout_srsue1) is the key of the first dict '''
        self.extract_kpis()
        kpi_tree = {}
        kpi_tree["log_" + self.name()] = self.log_kpi
        kpi_tree["csv_" + self.name()] = self.csv_kpi
        kpi_tree["stdout_" + self.name()] = self.stdout_kpi
        return kpi_tree

    def extract_kpis(self):
        ''' Use the srsLTE KPI analyzer module (part of srsLTE.git) if available to collect KPIs '''

        # Make sure this only runs once
        if self.csv_kpi is not None and self.log_kpi is not None and self.stdout_kpi is not None:
            return

        # Start with empty KPIs
        self.log_kpi = {}
        self.stdout_kpi = {}
        self.csv_kpi = {}

        # Stop application, copy back logs and process them
        if self.running():
            self.stop()
            self.cleanup()
        try:
            # Please make sure the srsLTE scripts folder is included in your PYTHONPATH env variable
            from kpi_analyzer import kpi_analyzer
            analyzer = kpi_analyzer(self.name())
            if self.log_file is not None:
                self.log_kpi = analyzer.get_kpi_from_logfile(self.log_file)
            if self.process.get_output_file('stdout') is not None:
                self.stdout_kpi = analyzer.get_kpi_from_stdout(self.process.get_output_file('stdout'))
            if self.metrics_file is not None:
                self.csv_kpi = analyzer.get_kpi_from_csv(self.metrics_file)
            # PHY errors for either UE or eNB components from parsed KPI vector as extra entry in dict
            self.log_kpi["num_phy_errors"] = analyzer.get_num_phy_errors(self.log_kpi)
        except ImportError:
            self.log("Can't load KPI analyzer module.")