# osmo_gsm_tester: context for individual test runs
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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

# These will be initialized before each test run.
# A test script can thus establish its context by doing:
# from osmo_gsm_tester.testenv import *

import sys

from .core import process
from .core import template
from .core import log as log_module
from .core import process as process_module
from .core import resource
from .core.event_loop import MainLoop

suite = None
log = None
dbg = None
err = None
wait = None
wait_no_raise = None
sleep = None
poll = None
prompt = None
Sms = None
process = None
tenv = None

class Timeout(Exception):
    pass

class TestEnv(log_module.Origin):
    def __init__(self, suite_run, test):
        super().__init__(log_module.C_TST, test.name())
        self.suite_run = suite_run
        self._test = test
        self._processes = []
        self.test_import_modules_to_clean_up = []
        self.objects_to_clean_up = None
        MainLoop.register_poll_func(self.poll)

    def test(self):
        return self._test

    def suite(self):
        return self.suite_run

    def remember_to_stop(self, process, respawn=False):
        '''Ask suite to monitor and manage lifecycle of the Process object. If a
        process managed by suite finishes before cleanup time, the current test
        will be marked as FAIL and end immediatelly. If respwan=True, then suite
        will respawn() the process instead.'''
        self._processes.insert(0, (process, respawn))

    def stop_processes(self):
        if len(self._processes) == 0:
            return
        strategy = process_module.ParallelTerminationStrategy()
        while self._processes:
            proc, _ = self._processes.pop()
            strategy.add_process(proc)
        strategy.terminate_all()

    def stop_process(self, process):
        'Remove process from monitored list and stop it'
        for proc_respawn in self._processes:
            proc, respawn = proc_respawn
            if proc == process:
                self._processes.remove(proc_respawn)
                proc.terminate()

    def register_for_cleanup(self, *obj):
        assert all([hasattr(o, 'cleanup') for o in obj])
        self.objects_to_clean_up = self.objects_to_clean_up or []
        self.objects_to_clean_up.extend(obj)

    def objects_cleanup(self):
        while self.objects_to_clean_up:
            obj = self.objects_to_clean_up.pop()
            try:
                obj.cleanup()
            except Exception:
                log_module.log_exn()

    def test_import_modules_register_for_cleanup(self, mod):
        '''
        Tests are required to call this API for any module loaded from its own
        lib subdir, because they are loaded in the global namespace. Otherwise
        later tests importing modules with the same name will re-use an already
        loaded module.
        '''
        if mod not in self.test_import_modules_to_clean_up:
            self.dbg('registering module %r for cleanup' % mod)
            self.test_import_modules_to_clean_up.append(mod)

    def test_import_modules_cleanup(self):
        while self.test_import_modules_to_clean_up:
            mod = self.test_import_modules_to_clean_up.pop()
            try:
                self.dbg('Cleaning up module %r' % mod)
                del sys.modules[mod.__name__]
                del mod
            except Exception:
                log_module.log_exn()

    def poll(self):
        for proc, respawn in self._processes:
            if proc.terminated():
                if respawn == True:
                    proc.respawn()
                else:
                    proc.log_stdout_tail()
                    proc.log_stderr_tail()
                    log_module.ctx(proc)
                    raise log_module.Error('Process ended prematurely: %s' % proc.name())

    def stop(self):
        # if sys.exit() called from signal handler (e.g. SIGINT), SystemExit
        # base exception is raised. Make sure to stop processes in this
        # finally section. Resources are automatically freed with 'atexit'.
        self.stop_processes()
        self.objects_cleanup()
        self.suite_run.reserved_resources.put_all()
        MainLoop.unregister_poll_func(self.poll)
        self.test_import_modules_cleanup()
        self.set_overlay_template_dir(None)

    def config_suite_specific(self):
        return self.suite_run.config_suite_specific()

    def config_test_specific(self):
        return self._test.config_test_specific()

    def set_overlay_template_dir(self, template_dir=None):
        '''Overlay a directory on top of default one when looking for
           directories. It must be called everytime a template file is updated.'''
        if template_dir is None:
            template.set_templates_dir(template.default_templates_dir())
        else:
            self.dbg('template dir overlay set: %s' % template_dir)
            template.set_templates_dir(template_dir, template.default_templates_dir())

    def prompt(self, *msgs, **msg_details):
        'ask for user interaction. Do not use in tests that should run automatically!'
        if msg_details:
            msgs = list(msgs)
            msgs.append('{%s}' %
                        (', '.join(['%s=%r' % (k,v)
                                    for k,v in sorted(msg_details.items())])))
        msg = ' '.join(msgs) or 'Hit Enter to continue'
        self.log('prompt:', msg)
        sys.__stdout__.write('\n\n--- PROMPT ---\n')
        sys.__stdout__.write(msg)
        sys.__stdout__.write('\n')
        sys.__stdout__.flush()
        entered = util.input_polling('> ', MainLoop.poll)
        self.log('prompt entered:', repr(entered))
        return entered

    def get_reserved_resource(self, resource_class_str, specifics=None):
        return self.suite_run.get_reserved_resource(resource_class_str, specifics)

    def ip_address(self, specifics=None):
        return self.get_reserved_resource(resource.R_IP_ADDRESS, specifics)

    def nitb(self, ip_address=None):
        from .obj.nitb_osmo import OsmoNitb
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoNitb(self, ip_address)

    def hlr(self, ip_address=None):
        from .obj.hlr_osmo import OsmoHlr
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoHlr(self, ip_address)

    def ggsn(self, ip_address=None):
        from .obj.ggsn_osmo import OsmoGgsn
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoGgsn(self, ip_address)

    def sgsn(self, hlr, ggsn, ip_address=None):
        from .obj import sgsn_osmo
        if ip_address is None:
            ip_address = self.ip_address()
        return sgsn_osmo.OsmoSgsn(self, hlr, ggsn, ip_address)

    def mgcpgw(self, ip_address=None, bts_ip=None):
        from .obj.mgcpgw_osmo import OsmoMgcpgw
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoMgcpgw(self, ip_address, bts_ip)

    def mgw(self, ip_address=None):
        from .obj.mgw_osmo import OsmoMgw
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoMgw(self, ip_address)

    def msc(self, hlr, mgcpgw, stp, ip_address=None):
        from .obj import msc_osmo
        if ip_address is None:
            ip_address = self.ip_address()
        return msc_osmo.OsmoMsc(self, hlr, mgcpgw, stp, ip_address)

    def bsc(self, msc, mgw, stp, ip_address=None):
        from .obj.bsc_osmo import OsmoBsc
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoBsc(self, msc, mgw, stp, ip_address)

    def stp(self, ip_address=None):
        from .obj.stp_osmo import OsmoStp
        if ip_address is None:
            ip_address = self.ip_address()
        return OsmoStp(self, ip_address)

    def ms_driver(self):
        from .obj.ms_driver import MsDriver
        ms = MsDriver(self)
        self.register_for_cleanup(ms)
        return ms

    def bts(self, specifics=None):
        from .obj.bts import Bts
        bts_obj = Bts.get_instance_by_type(self, self.get_reserved_resource(resource.R_BTS, specifics=specifics))
        bts_obj.set_lac(self.lac())
        bts_obj.set_rac(self.rac())
        bts_obj.set_cellid(self.cellid())
        bts_obj.set_bvci(self.bvci())
        self.register_for_cleanup(bts_obj)
        return bts_obj

    def modem(self, specifics=None):
        from .obj.ms import MS
        conf = self.get_reserved_resource(resource.R_MODEM, specifics=specifics)
        ms_obj = MS.get_instance_by_type(self, conf)
        self.register_for_cleanup(ms_obj)
        return ms_obj

    def modems(self, count):
        l = []
        for i in range(count):
            l.append(self.modem())
        return l

    def all_resources(self, resource_func):
        """Returns all yielded resource."""
        l = []
        while True:
            try:
                l.append(resource_func())
            except resource.NoResourceExn:
                return l

    def esme(self):
        from .obj.esme import Esme
        esme_obj = Esme(self.msisdn())
        self.register_for_cleanup(esme_obj)
        return esme_obj

    def run_node(self, specifics=None):
        from .obj.run_node import RunNode
        return RunNode.from_conf(self.get_reserved_resource(resource.R_RUN_NODE, specifics=specifics))

    def enb(self, specifics=None):
        from .obj.enb import eNodeB
        enb_obj = eNodeB.get_instance_by_type(self, self.get_reserved_resource(resource.R_ENB, specifics=specifics))
        self.register_for_cleanup(enb_obj)
        return enb_obj

    def epc(self, run_node=None):
        from .obj.epc import EPC
        if run_node is None:
            run_node = self.run_node()
        epc_obj = EPC.get_instance_by_type(self, run_node)
        self.register_for_cleanup(epc_obj)
        return epc_obj

    def osmocon(self, specifics=None):
        from .obj.osmocon import Osmocon
        conf = self.get_reserved_resource(resource.R_OSMOCON, specifics=specifics)
        osmocon_obj = Osmocon(self, conf=conf)
        self.register_for_cleanup(osmocon_obj)
        return osmocon_obj

    def iperf3srv(self, ip_address=None):
        from .obj.iperf3 import IPerf3Server
        if ip_address is None:
            ip_address = self.ip_address()
        iperf3srv_obj = IPerf3Server(self, ip_address)
        return iperf3srv_obj

    def msisdn(self):
        msisdn = self.suite_run.resource_pool().next_msisdn(self)
        self.log('using MSISDN', msisdn)
        return msisdn

    def lac(self):
        lac = self.suite_run.resource_pool().next_lac(self)
        self.log('using LAC', lac)
        return lac

    def rac(self):
        rac = self.suite_run.resource_pool().next_rac(self)
        self.log('using RAC', rac)
        return rac

    def cellid(self):
        cellid = self.suite_run.resource_pool().next_cellid(self)
        self.log('using CellId', cellid)
        return cellid

    def bvci(self):
        bvci = self.suite_run.resource_pool().next_bvci(self)
        self.log('using BVCI', bvci)
        return bvci


def setup(suite_run, _test):
    from .core.event_loop import MainLoop
    from .obj.sms import Sms as Sms_class

    global test, log, dbg, err, wait, wait_no_raise, sleep, poll, prompt, Sms, process, tenv

    test = _test
    log = test.log
    dbg = test.dbg
    err = test.err
    tenv = TestEnv(suite_run, _test)
    wait = MainLoop.wait
    wait_no_raise = MainLoop.wait_no_raise
    sleep = MainLoop.sleep
    poll = MainLoop.poll
    Sms = Sms_class
    process = process_module
    prompt = tenv.prompt
    return tenv

# vim: expandtab tabstop=4 shiftwidth=4
