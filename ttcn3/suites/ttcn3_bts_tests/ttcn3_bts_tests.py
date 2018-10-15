#!/usr/bin/env python3
import os
from mako.template import Template

from osmo_gsm_tester.testenv import *

hlr_dummy = suite.hlr()
mgw_dummy = suite.mgw()
stp_dummy = suite.stp()
msc_dummy = suite.msc(hlr_dummy, mgw_dummy, stp_dummy)
ggsn_dummy = suite.ggsn()
sgsn_dummy = suite.sgsn(hlr_dummy, ggsn_dummy)
bsc = suite.bsc(msc_dummy, mgw_dummy, stp_dummy)
bts = suite.bts()
osmocon = suite.osmocon()

bts.set_num_trx(1)
bts.set_trx_phy_channel(0, 0, 'CCCH+SDCCH4')
bts.set_trx_phy_channel(0, 1, 'TCH/F')
bts.set_trx_phy_channel(0, 2, 'TCH/F')
bts.set_trx_phy_channel(0, 3, 'TCH/F_PDCH')
bts.set_trx_phy_channel(0, 4, 'TCH/F_TCH/H_PDCH')
bts.set_trx_phy_channel(0, 5, 'TCH/H')
bts.set_trx_phy_channel(0, 6, 'SDCCH8')
bts.set_trx_phy_channel(0, 7, 'PDCH')

print('Starting CNI')
hlr_dummy.start()
stp_dummy.start()
msc_dummy.start()
mgw_dummy.start()

nat_rsl_ip = suite.ip_address().get('addr')
bsc.set_rsl_ip(nat_rsl_ip)
bsc.bts_add(bts)
sgsn_dummy.bts_add(bts)

bsc.start()
bts.start(keepalive=True)

print('Starting osmocon')
osmocon.start()

own_dir = os.path.dirname(os.path.realpath(__file__))
script_file = os.path.join(own_dir, 'scripts', 'run_ttcn3_docker.sh')
bts_tmpl_file = os.path.join(own_dir, 'scripts', 'BTS_Tests.cfg.tmpl')
script_run_dir = test.get_run_dir().new_dir('ttcn3')
bts_cfg_file = os.path.join(str(script_run_dir), 'BTS_Tests.cfg')
junit_ttcn3_dst_file = os.path.join(str(suite.trial.get_run_dir()), 'trial-') + suite.name() + '.xml'
if bts.bts_type() == 'osmo-bts-trx':
    pcu_available = True
    pcu_sk = bts.pcu_socket_path()
else: # PCU unix socket not available locally
    pcu_available = False
    pcu_sk = ''
docker_cmd = (script_file, str(script_run_dir), junit_ttcn3_dst_file, nat_rsl_ip, osmocon.l2_socket_path(), pcu_sk)

print('Creating template')
mytemplate = Template(filename=bts_tmpl_file)
r = mytemplate.render(btsvty_ctrl_hostname=bts.remote_addr(), pcu_available=pcu_available)
with open(bts_cfg_file, 'w') as f:
    f.write(r)


print('Starting TTCN3 tests')
proc = process.Process('ttcn3', script_run_dir, docker_cmd)
try:
    proc.launch()
    print('Starting TTCN3 launched, waiting until it finishes')
    proc.wait(timeout=3600)
except Exception as e:
    proc.terminate()
    raise e

if proc.result != 0:
    raise RuntimeError("run_ttcn3_docker.sh exited with error code %d" % proc.result)

print('Done')
