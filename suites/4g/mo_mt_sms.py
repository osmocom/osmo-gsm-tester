#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

#epc = suite.epc()
#enb = suite.enb()
ue = suite.modem()

#enb.start()
#epc.enb_add(enb)
#epc.start()

#wait(epc.enb_is_connected, enb)

#hss/epc.subscriber_add(ue)

#ue.connect(epc.mcc_mnc())
ue.connect()


print('waiting for modem to attach...')
#wait(ue.is_connected, msc.mcc_mnc())
sleep(10)
