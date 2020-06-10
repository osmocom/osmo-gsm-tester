#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

def print_results(cli, srv):
        cli.print_results()
        srv.print_results(cli.proto() == cli.PROTO_UDP)

def run_iperf3_cli_parallel(iperf3clients, ms_li, ready_cb):
    assert len(iperf3clients) == len(ms_li)
    procs = []
    for i in range(len(iperf3clients)):
        print("Running iperf3 client to %s through %r" % (str(iperf3clients[i]), repr(ms_li[i].tmp_ctx_id)))
        procs.append(iperf3clients[i].prepare_test_proc(iperf3clients[i].DIR_UL, ms_li[i].netns()))
    try:
        for proc in procs:
            proc.launch()
        if ready_cb:
            ready_cb(ms_li)
        for proc in procs:
            proc.wait()
    except Exception as e:
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                print("Exception while terminating process %r" % repr(process))
        raise e


def setup_run_iperf3_test_parallel(num_ms, ready_cb=None):
    hlr = tenv.hlr()
    bts = tenv.bts()
    pcu = bts.pcu()
    mgw_msc = tenv.mgw()
    mgw_bsc = tenv.mgw()
    stp = tenv.stp()
    ggsn = tenv.ggsn()
    sgsn = tenv.sgsn(hlr, ggsn)
    msc = tenv.msc(hlr, mgw_msc, stp)
    bsc = tenv.bsc(msc, mgw_bsc, stp)

    iperf3srv_addr = tenv.ip_address()
    servers = []
    clients = []
    ms_li = []
    for i in range(num_ms):
        iperf3srv = tenv.iperf3srv(iperf3srv_addr)
        iperf3srv.set_port(iperf3srv.DEFAULT_SRV_PORT + i)
        servers.append(iperf3srv)

        iperf3cli = iperf3srv.create_client()
        clients.append(iperf3cli)

        ms = tenv.modem()
        ms_li.append(ms)

    bsc.bts_add(bts)
    sgsn.bts_add(bts)

    for iperf3srv in servers:
        print('start iperfv3 server %s...' % str(iperf3srv) )
        iperf3srv.start()

    print('start network...')
    hlr.start()
    stp.start()
    ggsn.start()
    sgsn.start()
    msc.start()
    mgw_msc.start()
    mgw_bsc.start()
    bsc.start()

    bts.start()
    wait(bsc.bts_is_connected, bts)
    print('Waiting for bts to be ready...')
    wait(bts.ready_for_pcu)
    pcu.start()

    for ms in ms_li:
        hlr.subscriber_add(ms)
        ms.connect(msc.mcc_mnc())
        ms.attach()
        ms.log_info()

    print('waiting for modems to attach...')
    for ms in ms_li:
        wait(ms.is_registered, msc.mcc_mnc())
    wait(msc.subscriber_attached, *ms_li)

    print('waiting for modems to attach to data services...')
    for ms in ms_li:
        wait(ms.is_attached)
        # We need to use inet46 since ofono qmi only uses ipv4v6 eua (OS#2713)
        ctx_id_v4 = ms.activate_context(apn='inet46', protocol=ms.CTX_PROT_IPv4)
        print("Setting up data plan for %r" % repr(ctx_id_v4))
        ms.setup_context_data_plane(ctx_id_v4)
        setattr(ms, 'tmp_ctx_id', ctx_id_v4)

    run_iperf3_cli_parallel(clients, ms_li, ready_cb)

    for i in range(num_ms):
        servers[i].stop()
        print("Results for %s through %r" % (str(servers[i]), repr(ms_li[i].tmp_ctx_id)))
        print_results(clients[i], servers[i])

    for ms in ms_li:
        ms.deactivate_context(ms.tmp_ctx_id)
        delattr(ms, 'tmp_ctx_id')
