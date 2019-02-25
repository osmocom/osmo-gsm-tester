#!/usr/bin/env python3
"""
Run a network registration with a 'massive' amount of MS
using the ms_driver infrastructure.
"""
from osmo_gsm_tester.testenv import *

print('use resources...')
nitb = suite.nitb()
bts = suite.bts()
ms_driver = suite.ms_driver()
modems = suite.all_resources(suite.modem)

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()
wait(nitb.bts_is_connected, bts)

# Configure all MS that are available to this test.
for modem in modems:
    nitb.subscriber_add(modem)
    ms_driver.subscriber_add(modem)

# Run the base test.
ms_driver.run_test()

# Print stats
ms_driver.print_stats()
