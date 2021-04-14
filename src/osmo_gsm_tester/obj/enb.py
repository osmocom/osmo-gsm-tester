# osmo_gsm_tester: base classes to share code among eNodeB subclasses.
#
# Copyright (C) 2020 by sysmocom - s.f.m.c. GmbH
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
from ..core import log, config
from ..core import schema
from . import run_node
from .gnuradio_zmq_broker import GrBroker

def on_register_schemas():
    resource_schema = {
        'label': schema.STR,
        'type': schema.STR,
        'gtp_bind_addr': schema.IPV4,
        'id': schema.UINT,
        'num_prb': schema.UINT,
        'duplex': schema.STR,
        'tdd_uldl_config': schema.UINT,
        'tdd_special_subframe_pattern': schema.UINT,
        'transmission_mode': schema.LTE_TRANSMISSION_MODE,
        'rx_ant': schema.STR,
        'tx_gain': schema.UINT,
        'rx_gain': schema.UINT,
        'rf_dev_type': schema.STR,
        'rf_dev_args': schema.STR,
        'rf_dev_sync': schema.STR,
        'additional_args[]': schema.STR,
        'inactivity_timer': schema.INT,
        'enable_measurements': schema.BOOL_STR,
        'enable_dl_awgn': schema.BOOL_STR,
        'dl_awgn_snr': schema.INT,
        'cipher_list[]': schema.CIPHER_4G,
        'integrity_list[]': schema.INTEGRITY_4G,
        'a1_report_type': schema.STR,
        'a1_report_value': schema.INT,
        'a1_hysteresis': schema.INT,
        'a1_time_to_trigger': schema.INT,
        'a2_report_type': schema.STR,
        'a2_report_value': schema.INT,
        'a2_hysteresis': schema.INT,
        'a2_time_to_trigger': schema.INT,
        'a3_report_type': schema.STR,
        'a3_report_value': schema.INT,
        'a3_hysteresis': schema.INT,
        'a3_time_to_trigger': schema.INT,
        'num_cells': schema.UINT,
        'cell_list[].cell_id': schema.UINT,
        'cell_list[].rf_port': schema.UINT,
        'cell_list[].pci': schema.UINT,
        'cell_list[].ncell_list[].enb_id': schema.UINT,
        'cell_list[].ncell_list[].cell_id': schema.UINT,
        'cell_list[].ncell_list[].pci': schema.UINT,
        'cell_list[].ncell_list[].dl_earfcn': schema.UINT,
        'cell_list[].scell_list[]': schema.UINT,
        'cell_list[].dl_earfcn': schema.UINT,
        'cell_list[].root_seq_idx': schema.UINT,
        'cell_list[].tac': schema.UINT,
        'cell_list[].dl_rfemu.type': schema.STR,
        'cell_list[].dl_rfemu.addr': schema.IPV4,
        'cell_list[].dl_rfemu.ports[]': schema.UINT,
        }
    for key, val in run_node.RunNode.schema().items():
        resource_schema['run_node.%s' % key] = val
    schema.register_resource_schema('enb', resource_schema)

class eNodeB(log.Origin, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, testenv, conf, name):
        super().__init__(log.C_RUN, '%s' % name)
        self._conf = conf
        self._run_node = run_node.RunNode.from_conf(conf.get('run_node', {}))
        self._gtp_bind_addr = conf.get('gtp_bind_addr', None)
        if self._gtp_bind_addr is None:
            self._gtp_bind_addr = self._run_node.run_addr()
        label = conf.get('label', None)
        if label is not None:
            self.set_name('%s_%s_%s' % (name, label, self._run_node.run_addr()))
        else:
            self.set_name('%s_%s' % (name, self._run_node.run_addr()))
        self._txmode = 0
        self._id = None
        self._duplex = None
        self._num_prb = 0
        self._num_cells = None
        self._epc = None
        self.gen_conf = None
        self.gr_broker = GrBroker.ref()
        self.gr_broker.register_enb(self)
        self._use_gr_broker = False

    def using_grbroker(self, cfg_values):
        # whether we are to use Grbroker in between ENB and UE.
        # Initial checks:
        if cfg_values['enb'].get('rf_dev_type') != 'zmq':
            return False
        cell_list = cfg_values['enb']['cell_list']
        use_match = False
        notuse_match = False
        for cell in cell_list:
            if cell.get('dl_rfemu', False) and cell['dl_rfemu'].get('type', None) == 'gnuradio_zmq':
                use_match = True
            else:
                notuse_match = True
        if use_match and notuse_match:
            raise log.Error('Some Cells are configured to use gnuradio_zmq and some are not, unsupported')
        return use_match

    def calc_required_zmq_ports(self, cfg_values):
        cell_list = cfg_values['enb']['cell_list']
        return len(cell_list) * self.num_ports() # *2 if MIMO

    def calc_required_zmq_ports_joined_earfcn(self, cfg_values):
        #gr_broker will join the earfcns, so we need to count uniqe earfcns:
        cell_list = cfg_values['enb']['cell_list']
        earfcn_li = []
        [earfcn_li.append(int(cell['dl_earfcn'])) for cell in cell_list if int(cell['dl_earfcn']) not in earfcn_li]
        return len(earfcn_li) * self.num_ports() # *2 if MIMO


    def assign_enb_zmq_ports(self, cfg_values, port_name, base_port):
        port_offset = 0
        cell_list = cfg_values['enb']['cell_list']
        for cell in cell_list:
            cell[port_name] = base_port + port_offset
            port_offset += self.num_ports()
        # TODO: do we need to assign cell_list back?

    def assign_enb_zmq_ports_joined_earfcn(self, cfg_values, port_name, base_port):
        # TODO: Set in cell one bind port per unique earfcn, this is where UE will connect to when we use grbroker.
        cell_list = cfg_values['enb']['cell_list']
        earfcn_li = []
        [earfcn_li.append(int(cell['dl_earfcn'])) for cell in cell_list if int(cell['dl_earfcn']) not in earfcn_li]
        for cell in cell_list:
            cell[port_name] = base_port + earfcn_li.index(int(cell['dl_earfcn'])) * self.num_ports()

    def configure(self, config_specifics_li):
        values = dict(enb=config.get_defaults('enb'))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(enb=config.get_defaults(config_specifics)))
        config.overlay(values, dict(enb=self.testenv.suite().config().get('enb', {})))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(enb=self.testenv.suite().config().get(config_specifics, {})))
        config.overlay(values, dict(enb=self._conf))
        self._id = int(values['enb'].get('id', None))
        assert self._id is not None
        self._duplex = values['enb'].get('duplex', None)
        assert self._duplex
        self._num_prb = int(values['enb'].get('num_prb', None))
        assert self._num_prb
        self._txmode = int(values['enb'].get('transmission_mode', None))
        assert self._txmode
        config.overlay(values, dict(enb={ 'num_ports': self.num_ports() }))
        self._inactivity_timer = int(values['enb'].get('inactivity_timer', None))
        assert self._inactivity_timer
        assert self._epc is not None
        config.overlay(values, dict(enb={ 'addr': self.addr() }))
        config.overlay(values, dict(enb={ 'mme_addr': self._epc.addr() }))
        config.overlay(values, dict(enb={ 'gtp_bind_addr': self._gtp_bind_addr }))
        self._num_cells = int(values['enb'].get('num_cells', None))
        assert self._num_cells

        # adjust cell_list to num_cells length:
        len_cell_list = len(values['enb']['cell_list'])
        if len_cell_list >= self._num_cells:
            values['enb']['cell_list'] = values['enb']['cell_list'][:self._num_cells]
        else:
            raise log.Error('enb.cell_list items (%d) < enb.num_cells (%d) attribute!' % (len_cell_list, self._num_cells))
        # adjust scell list (to only contain values available in cell_list):
        cell_id_list = [c['cell_id'] for c in values['enb']['cell_list']]
        for i in range(len(values['enb']['cell_list'])):
            scell_list_old = values['enb']['cell_list'][i]['scell_list']
            scell_list_new = []
            for scell_id in scell_list_old:
                if scell_id in cell_id_list:
                    scell_list_new.append(scell_id)
            values['enb']['cell_list'][i]['scell_list'] = scell_list_new

        # Assign ZMQ ports to each Cell/EARFCN.
        if values['enb'].get('rf_dev_type') == 'zmq':
            resourcep = self.testenv.suite().resource_pool()
            num_ports = self.calc_required_zmq_ports(values)
            num_ports_joined_earfcn = self.calc_required_zmq_ports_joined_earfcn(values)
            ue_bind_port = self.ue.zmq_base_bind_port()
            enb_bind_port = resourcep.next_zmq_port_range(self, num_ports)
            self.assign_enb_zmq_ports(values, 'zmq_enb_bind_port', enb_bind_port)
            # If we are to use a GrBroker, then initialize here to have remote zmq ports available:
            self._use_gr_broker = self.using_grbroker(values)
            if self._use_gr_broker:
                zmq_enb_peer_port = resourcep.next_zmq_port_range(self, num_ports)
                self.assign_enb_zmq_ports(values, 'zmq_enb_peer_port', zmq_enb_peer_port) # These are actually bound to GrBroker
                self.assign_enb_zmq_ports_joined_earfcn(values, 'zmq_ue_bind_port', ue_bind_port) # This is were GrBroker binds on the UE side
                zmq_ue_peer_port = resourcep.next_zmq_port_range(self, num_ports_joined_earfcn)
                self.assign_enb_zmq_ports_joined_earfcn(values, 'zmq_ue_peer_port', zmq_ue_peer_port) # This is were GrBroker binds on the UE side
                # Already set gen_conf here in advance since gr_broker needs the cell list
                self.gen_conf = values
                self.gr_broker.start()
            else:
                self.assign_enb_zmq_ports(values, 'zmq_enb_peer_port', ue_bind_port)
                self.assign_enb_zmq_ports(values, 'zmq_ue_bind_port', ue_bind_port) #If no broker we need to match amount of ports
                self.assign_enb_zmq_ports(values, 'zmq_ue_peer_port', enb_bind_port)

        return values

    def id(self):
        return self._id

    def num_ports(self):
        if self._txmode == 1:
            return 1
        return 2

    def num_cells(self):
        return self._num_cells

########################
# PUBLIC - INTERNAL API
########################
    def cleanup(self):
        'Nothing to do by default. Subclass can override if required.'
        if self.gr_broker:
            self.gr_broker.unregister_enb(self)
            GrBroker.unref()
            self.gr_broker = None

    def num_prb(self):
        return self._num_prb

    #reference: srsLTE.git srslte_symbol_sz()
    def num_prb2symbol_sz(self, num_prb):
        if num_prb == 6:
            return 128
        if num_prb == 50:
            return 768
        if num_prb == 75:
            return 1024
        return 1536

        raise log.Error('invalid num_prb %r', num_prb)

    def num_prb2base_srate(self, num_prb):
        return self.num_prb2symbol_sz(num_prb) * 15 * 1000

    def get_zmq_rf_dev_args(self, cfg_values):
        base_srate = self.num_prb2base_srate(self.num_prb())

        if self._use_gr_broker:
            ul_rem_addr = self.gr_broker.addr()
        else:
            ul_rem_addr = self.ue.addr()

        rf_dev_args = 'fail_on_disconnect=true,log_trx_timeout=true,trx_timeout_ms=8000'
        idx = 0
        cell_list = cfg_values['enb']['cell_list']
        # Define all 8 possible RF ports (2x CA with 2x2 MIMO)
        for cell in cell_list:
            rf_dev_args += ',tx_port%u=tcp://%s:%u' %(idx, self.addr(), cell['zmq_enb_bind_port'] + 0)
            if self.num_ports() > 1:
                rf_dev_args += ',tx_port%u=tcp://%s:%u' %(idx + 1, self.addr(), cell['zmq_enb_bind_port'] + 1)
            rf_dev_args += ',rx_port%u=tcp://%s:%u' %(idx, ul_rem_addr, cell['zmq_enb_peer_port'] + 0)
            if self.num_ports() > 1:
                rf_dev_args += ',rx_port%u=tcp://%s:%u' %(idx + 1, ul_rem_addr, cell['zmq_enb_peer_port'] + 1)
            idx += self.num_ports()

        rf_dev_args += ',id=enb,base_srate=' + str(base_srate)
        return rf_dev_args

    def get_zmq_rf_dev_args_for_ue(self, ue):
        cell_list = self.gen_conf['enb']['cell_list']
        rf_dev_args = ''
        idx = 0
        earfcns_done = []
        for cell in cell_list:
            if self._use_gr_broker:
                if cell['dl_earfcn'] in earfcns_done:
                    continue
                earfcns_done.append(cell['dl_earfcn'])
            rf_dev_args += ',tx_port%u=tcp://%s:%u' %(idx, ue.addr(), cell['zmq_ue_bind_port'] + 0)
            if self.num_ports() > 1:
                rf_dev_args += ',tx_port%u=tcp://%s:%u' %(idx + 1, ue.addr(), cell['zmq_ue_bind_port'] + 1)
            rf_dev_args += ',rx_port%u=tcp://%s:%u' %(idx, self.addr(), cell['zmq_ue_peer_port'] + 0)
            if self.num_ports() > 1:
                rf_dev_args += ',rx_port%u=tcp://%s:%u' %(idx + 1, self.addr(), cell['zmq_ue_peer_port'] + 1)
            idx += self.num_ports()
        # remove trailing comma:
        if rf_dev_args[0] == ',':
            return rf_dev_args[1:]
        return rf_dev_args

    def get_instance_by_type(testenv, conf):
        """Allocate a ENB child class based on type. Opts are passed to the newly created object."""
        enb_type = conf.get('type')
        if enb_type is None:
            raise RuntimeError('ENB type is not defined!')

        if enb_type == 'amarisoftenb':
            from .enb_amarisoft import AmarisoftENB
            enb_class = AmarisoftENB
        elif enb_type == 'srsenb':
            from .enb_srs import srsENB
            enb_class = srsENB
        else:
            raise log.Error('ENB type not supported:', enb_type)
        return  enb_class(testenv, conf)

###################
# PUBLIC (test API included)
###################
    @abstractmethod
    def start(self, epc):
        'Starts ENB, it will connect to "epc"'
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def ue_add(self, ue):
        pass

    @abstractmethod
    def running(self):
        pass

    @abstractmethod
    def ue_max_rate(self, downlink=True, num_carriers=1):
        pass

    @abstractmethod
    def get_rfemu(self, cell=0, dl=True):
        'Get rfemu.RFemulation subclass implementation object for given cell index and direction.'
        pass

    def addr(self):
        return self._run_node.run_addr()

    @abstractmethod
    def get_counter(self, counter_name):
        pass

    @abstractmethod
    def get_kpis(self):
        pass

# vim: expandtab tabstop=4 shiftwidth=4