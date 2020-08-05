#!/usr/bin/env python3
import os
from mako.template import Template

from osmo_gsm_tester.testenv import *

def run_ttcn3(tenv, testdir, bts, osmocon, nat_rsl_ip,
              ttcn3_test_groups = [],
              ttcn3_test_extra_module_params=""):
    own_dir = testdir
    script_file = os.path.join(testdir, 'scripts', 'run_ttcn3_docker.sh')
    bts_tmpl_file = os.path.join(testdir, 'scripts', 'BTS_Tests.cfg.tmpl')
    script_run_dir = tenv.test().get_run_dir().new_dir('ttcn3')
    bts_cfg_file = os.path.join(str(script_run_dir), 'BTS_Tests.cfg')
    junit_ttcn3_dst_file = os.path.join(str(tenv.suite().trial().get_run_dir()), 'trial-' + tenv.suite().name() +  '.' + tenv.test().module_name() + '.xml')
    if bts.bts_type() == 'osmo-bts-trx':
        pcu_available = True
        pcu_sk = bts.pcu_socket_path()
    else: # PCU unix socket not available locally
        pcu_available = False
        pcu_sk = ''
    docker_cmd = (script_file, str(script_run_dir), junit_ttcn3_dst_file, nat_rsl_ip, osmocon.l2_socket_path(), pcu_sk)

    print('Creating template')
    mytemplate = Template(filename=bts_tmpl_file)
    r = mytemplate.render(btsvty_ctrl_hostname=bts.remote_addr(),
                          pcu_available=pcu_available,
                          ttcn3_test_groups=ttcn3_test_groups,
                          ttcn3_test_extra_module_params=ttcn3_test_extra_module_params)
    with open(bts_cfg_file, 'w') as f:
        f.write(r)


    print('Starting TTCN3 test suite')
    proc = process.Process('ttcn3', script_run_dir, docker_cmd)
    try:
        proc.launch()
        print('TTCN3 test suite launched, waiting until it finishes')
        proc.wait(timeout=3600)
    except Exception as e:
        proc.terminate()
        raise e

    if proc.result != 0:
        raise RuntimeError("run_ttcn3_docker.sh exited with error code %d" % proc.result)

    print('Done')
