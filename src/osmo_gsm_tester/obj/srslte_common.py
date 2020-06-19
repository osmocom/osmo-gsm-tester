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

class srslte_common(): # don't inherit from log.Origin here but instead use .name() from whoever inherits from us

  def __init__(self):
    self.log_file = None
    self.process = None
    self.metrics_file = None

  def get_kpis(self):
      ''' Use the srsLTE KPI analyzer module (part of srsLTE.git) if available to collect KPIs '''
      kpis = {}
      try:
          # Please make sure the srsLTE scripts folder is included in your PYTHONPATH env variable
          from kpi_analyzer import kpi_analyzer
          analyzer = kpi_analyzer(self.name())
          if self.log_file is not None:
              kpis["log_" + self.name()] = analyzer.get_kpi_from_logfile(self.log_file)
          if self.process.get_output_file('stdout') is not None:
              kpis["stdout_" + self.name()] = analyzer.get_kpi_from_stdout(self.process.get_output_file('stdout'))
          if self.metrics_file is not None:
              kpis["csv_" + self.name()] = analyzer.get_kpi_from_csv(self.metrics_file)
      except ImportError:
          self.log("Can't load KPI analyzer module.")

      return kpis
