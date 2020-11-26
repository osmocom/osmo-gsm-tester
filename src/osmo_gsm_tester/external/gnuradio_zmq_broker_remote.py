#!/usr/bin/env python2

# This is script is aimed at being copied to some remote target host where it
# will be run by osmo-gsm-tester through ssh

from distutils.version import StrictVersion

from gnuradio.fft import window
from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
import sys
import json
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import zeromq
import socket
import argparse
from signal import *

class GrBroker(gr.top_block):

    def __init__(self, args, cfg):
        gr.top_block.__init__(self, "InterENB Handover Flowgraph")

        ##################################################
        # Variables
        ##################################################
        self.args = args
        self.cfg = cfg
        self.samp_rate = samp_rate = 23040000
        self.relative_gain = relative_gain = 1.0
        self.blocks_add = {}

        ##################################################
        # Blocks
        ##################################################

        # Build ENB side + connect to per stream multilier:
        for enb in self.cfg['enb']:
            for it in enb:
                source_addr = 'tcp://%s:%u' % (it['peer_addr'].encode('utf-8'), it['peer_port'])
                sink_addr = 'tcp://%s:%u' % (args.bind_addr, it['bind_port'])
                print('enb: earfcn=%u source=%r sink=%r' % (it['earfcn'], source_addr, sink_addr))
                it['gr_block_zmq_source'] = zeromq.req_source(gr.sizeof_gr_complex, 1, source_addr, 100, False, -1)
                it['gr_block_zmq_sink'] = zeromq.rep_sink(gr.sizeof_gr_complex, 1, sink_addr, 100, False, -1)
                it['gr_block_multiply'] = blocks.multiply_const_cc(relative_gain)
                it['gr_block_multiply'].set_block_alias('relative_gain %s' % source_addr)
                self.connect((it['gr_block_zmq_source'], 0), (it['gr_block_multiply'], 0))
                if it['use_mimo']:
                    source_addr = 'tcp://%s:%u' % (it['peer_addr'].encode('utf-8'), it['peer_port'] + 1)
                    sink_addr = 'tcp://%s:%u' % (args.bind_addr, it['bind_port'] + 1)
                    print('enb: earfcn=%u source=%r sink=%r (MIMO)' % (it['earfcn'], source_addr, sink_addr))
                    it['gr_block_zmq_source2'] = zeromq.req_source(gr.sizeof_gr_complex, 1, source_addr, 100, False, -1)
                    it['gr_block_zmq_sink2'] = zeromq.rep_sink(gr.sizeof_gr_complex, 1, sink_addr, 100, False, -1)
                    it['gr_block_multiply2'] = blocks.multiply_const_cc(relative_gain)
                    it['gr_block_multiply2'].set_block_alias('relative_gain %s' % source_addr)
                    self.connect((it['gr_block_zmq_source2'], 0), (it['gr_block_multiply2'], 0))

        # Build UE side:
        for ue in self.cfg['ue']:
            for it in ue:
                source_addr = 'tcp://%s:%u' % (it['peer_addr'].encode('utf-8'), it['peer_port'])
                sink_addr = 'tcp://%s:%u' % (args.bind_addr, it['bind_port'])
                print('ue: earfcn=%u source=%r sink=%r' % (it['earfcn'], source_addr, sink_addr))
                it['gr_block_zmq_source'] = zeromq.req_source(gr.sizeof_gr_complex, 1, source_addr, 100, False, -1)
                it['gr_block_zmq_sink'] = zeromq.rep_sink(gr.sizeof_gr_complex, 1, sink_addr, 100, False, -1)
                if it['use_mimo']:
                    source_addr = 'tcp://%s:%u' % (it['peer_addr'].encode('utf-8'), it['peer_port'] + 1)
                    sink_addr = 'tcp://%s:%u' % (args.bind_addr, it['bind_port'] + 1)
                    print('ue: earfcn=%u source=%r sink=%r (MIMO)' % (it['earfcn'], source_addr, sink_addr))
                    it['gr_block_zmq_source2'] = zeromq.req_source(gr.sizeof_gr_complex, 1, source_addr, 100, False, -1)
                    it['gr_block_zmq_sink2'] = zeromq.rep_sink(gr.sizeof_gr_complex, 1, sink_addr, 100, False, -1)

        # Create per EARFCN adder (only 2->1 supported so far)
        earfcn_li = self.calc_earfcn_list()
        blocks_add_next_avail_port = {}
        for earfcn in earfcn_li:
                self.blocks_add[earfcn] = blocks.add_vcc(1)
                blocks_add_next_avail_port[earfcn] = 0
        # Connect the ENB-side multipliers to the Adder input ports:
        idx = 0
        for enb in self.cfg['enb']:
            for it in enb:
                print('Connecting ENB port %u to Adder[%u] for earfcn %u' % (it['bind_port'], blocks_add_next_avail_port[it['earfcn']], it['earfcn']))
                self.connect((it['gr_block_multiply'], 0), (self.blocks_add[it['earfcn']], blocks_add_next_avail_port[it['earfcn']]))
                # TODO: if it['use_mimo'], connect it['gr_block_multiply2'] to some adder...
                blocks_add_next_avail_port[it['earfcn']] += 1

        # Connect the Adder to the UE-side (Dl):
        for earfcn, bl_add in self.blocks_add.items():
            for ue in self.cfg['ue']:
                for it in ue:
                    if it['earfcn'] != earfcn:
                        continue
                    print('Connecting Adder for earfcn %u to UE port %u' % (earfcn, it['bind_port']))
                    self.connect((bl_add, 0), (it['gr_block_zmq_sink'], 0))
                    # TODO: if it['use_mimo'], connect some adder to it['gr_block_zmq_sink2']...

        # UL: Connect 1 UE port splitting it into N ENB ports:
        for ue in self.cfg['ue']:
            for it_ue in ue:
                for enb in self.cfg['enb']:
                    for it_enb in enb:
                        if it_ue['earfcn'] != it_enb['earfcn']:
                            continue
                        print('connecting UE port %u to ENB port %u, earfcn=%u' % (it_ue['bind_port'], it_enb['bind_port'], it_enb['earfcn']))
                        self.connect((it_ue['gr_block_zmq_source'], 0), (it_enb['gr_block_zmq_sink'], 0))
                        if it_ue['use_mimo'] and it_enb['use_mimo']:
                            self.connect((it_ue['gr_block_zmq_source2'], 0), (it_enb['gr_block_zmq_sink2'], 0))

    def calc_earfcn_list(self):
        earfcn_li = []
        for enb in self.cfg['enb']:
            for it in enb:
                if it['earfcn'] not in earfcn_li:
                    earfcn_li.append(it['earfcn'])
        return earfcn_li

    def set_relative_gain(self, port, relative_gain):
        for enb in self.cfg['enb']:
            for it in enb:
                if it['bind_port'] == port:
                    print('setting port %u rel_gain to %f' % (port, relative_gain))
                    it['gr_block_multiply'].set_k(relative_gain)
                    return

def mainloop(sock, broker):
    while True:
        chunk = sock.recv(4096)
        stringdata = chunk.decode('utf-8')
        msg = json.loads(stringdata)
        print('Received msg: %s' % msg)

        if msg['action'] == 'exit':
            print('Received exit command. Stopping radio...')
            return
        elif msg['action'] == 'set_relative_gain':
            broker.set_relative_gain(msg['port'], msg['rel_gain'])
        else:
            print('Unknwon action for message: %s' % msg)


def sig_handler_cleanup(signum, frame):
    print("killed by signal %d" % signum)
    # This sys.exit() will raise a SystemExit base exception at the current
    # point of execution. Code must be prepared to clean system-wide resources
    # by using the "finally" section. This allows at the end 'atexit' hooks to
    # be called before exiting.
    sys.exit(1)

def main():

    for sig in (SIGINT, SIGTERM, SIGQUIT, SIGPIPE, SIGHUP):
        signal(sig, sig_handler_cleanup)

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bind-addr', dest='bind_addr', help="Address where local sockets are bound to")
    parser.add_argument('-c', '--ctrl-port', dest='ctrl_port', type=int, default=5005, help="Port where CTRL interface is bound to")
    args = parser.parse_args()

    print('bind_addr:', repr(args.bind_addr))
    print('ctrl_port:', repr(args.ctrl_port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind_addr, args.ctrl_port))

    broker = None
    try:
        print('waiting for configuration on UDP socket...')
        chunk = sock.recv(4096)
        print('Received udp packet')
        stringdata = chunk.decode('utf-8')
        cfg = json.loads(stringdata)
        print('Got config:', stringdata)
        broker = GrBroker(args, cfg)
        print('Starting...')
        broker.start()
        print('in mainloop')
        mainloop(sock, broker)
    except KeyboardInterrupt:
        pass
    print('main loop ended, exiting...')
    # closing flowgraph and socket
    sock.close()
    if broker:
        broker.stop()
        broker.wait()


if __name__ == '__main__':
    main()
    print("exit")
