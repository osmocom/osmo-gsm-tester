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
    self.kpis = None

  def sleep_after_stop(self):
    # Only sleep once
    if self.stop_sleep_time > 0:
        MainLoop.sleep(self.stop_sleep_time)
        self.stop_sleep_time = 0

  def stop(self):
      self.testenv.stop_process(self.process)
      self.sleep_after_stop()

  def get_kpis(self):
      ''' Return all KPI '''
      if self.kpis is None:
          self.extract_kpis()
      return self.kpis

  def get_log_kpis(self):
      ''' Return KPIs extracted from log '''
      if self.kpis is None:
          self.extract_kpis()

      # Use log KPIs if they exist for this node
      if "log_" + self.name() in self.kpis:
          log_kpi = self.kpis["log_" + self.name()]
      else:
          log_kpi = {}

      # Make sure we have the errors and warnings counter in the dict
      if 'total_errors' not in log_kpi:
          log_kpi['total_errors'] = 0
      if 'total_warnings' not in log_kpi:
          log_kpi['total_warnings'] = 0
      return log_kpi

  def extract_kpis(self):
      ''' Use the srsLTE KPI analyzer module (part of srsLTE.git) if available to collect KPIs '''

      # Stop application, copy back logs and process them
      if self.running():
          self.stop()
          self.cleanup()

      self.kpis = {}
      try:
          # Please make sure the srsLTE scripts folder is included in your PYTHONPATH env variable
          from kpi_analyzer import kpi_analyzer
          analyzer = kpi_analyzer(self.name())
          if self.log_file is not None:
              self.kpis["log_" + self.name()] = analyzer.get_kpi_from_logfile(self.log_file)
          if self.process.get_output_file('stdout') is not None:
              self.kpis["stdout_" + self.name()] = analyzer.get_kpi_from_stdout(self.process.get_output_file('stdout'))
          if self.metrics_file is not None:
              self.kpis["csv_" + self.name()] = analyzer.get_kpi_from_csv(self.metrics_file)
      except ImportError:
          self.log("Can't load KPI analyzer module.")
          self.kpis = {}

      return self.kpis

   def get_num_phy_errors(self, kpi):
       """ Use KPI analyzer to calculate the number PHY errors for either UE or eNB components from parsed KPI vector """
       try:
           # Same as above, make sure the srsLTE scripts folder is included in your PYTHONPATH env variable
           from kpi_analyzer import kpi_analyzer
           analyzer = kpi_analyzer(self.name())
           return analyzer.get_num_phy_errors(kpi)
       except ImportError:
           self.log("Can't load KPI analyzer module.")
           return 0