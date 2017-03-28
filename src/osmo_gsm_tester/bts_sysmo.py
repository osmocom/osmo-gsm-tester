# osmo_gsm_tester: specifics for running a sysmoBTS
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

from . import log, config, util, template

class SysmoBts(log.Origin):
    suite_run = None
    nitb = None
    run_dir = None

    def __init__(self, suite_run, conf):
        self.suite_run = suite_run
        self.conf = conf
        self.set_name('osmo-bts-sysmo')
        self.set_log_category(log.C_RUN)

    def start(self):
        if self.nitb is None:
            raise RuntimeError('BTS needs to be added to a NITB before it can be started')
        self.log('Starting sysmoBTS to connect to', self.nitb)
        self.run_dir = util.Dir(self.suite_run.trial.get_run_dir().new_dir(self.name()))
        self.configure()
        self.err('SysmoBts is not yet implemented')

    def configure(self):
        if self.nitb is None:
            raise RuntimeError('BTS needs to be added to a NITB before it can be configured')
        self.config_file = self.run_dir.new_file('osmo-bts-sysmo.cfg')
        self.dbg(config_file=self.config_file)

        values = { 'osmo_bts_sysmo': config.get_defaults('osmo_bts_sysmo') }
        config.overlay(values, self.suite_run.config())
        config.overlay(values, { 'osmo_bts_sysmo': { 'oml_remote_ip': self.nitb.addr() } })
        config.overlay(values, { 'osmo_bts_sysmo': self.conf })
        self.dbg(conf=values)

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-bts-sysmo.cfg', values)
            self.dbg(r)
            f.write(r)

    def conf_for_nitb(self):
        values = config.get_defaults('nitb_bts')
        config.overlay(values, config.get_defaults('osmo_bts_sysmo'))
        config.overlay(values, self.conf)
        config.overlay(values, { 'type': 'sysmobts' })
        self.dbg(conf=values)
        return values

    def set_nitb(self, nitb):
        self.nitb = nitb

# vim: expandtab tabstop=4 shiftwidth=4
