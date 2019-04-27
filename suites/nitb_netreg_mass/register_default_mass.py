#!/usr/bin/env python3
"""
Runs a network registration with a 'massive' amount of MS
using the ms_driver infrastructure.
"""
from osmo_gsm_tester.testenv import *
from datetime import timedelta

print('Claiming resources for the test')
nitb = suite.nitb()
bts = suite.bts()
ms_driver = suite.ms_driver()
modems = suite.all_resources(suite.modem)

print('Launching a simple network')
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

# Print the stats of the run.
ms_driver.print_stats()

# Evaluate if this run was successful or not. Our initial acceptance criteria
# is quite basic but it should allow us to scale to a larger number of MS and
# reasons (e.g. have a full BCCH).
#
# 99% of LUs should complete
# 99% of successful LUs should complete within 10s.
stats = ms_driver.get_stats()
if len(modems) > 0 and stats.num_completed < 1:
    raise Exception("No run completed.")
completion_ratio = stats.num_completed / stats.num_attempted

# Verify that 99% of LUs completed.
if completion_ratio < 0.99:
    raise Exception("Completion ratio of %f%% lower than threshold." % (completion_ratio * 100.0))

# Check how many results are below our threshold.
acceptable_delay = timedelta(seconds=30)
quick_enough = len(ms_driver.lus_less_than(acceptable_delay))
latency_ratio = quick_enough / stats.num_attempted
if latency_ratio < 0.99:
    raise Exception("Latency ratio of %f%% lower than threshold." % (latency_ratio * 100.0))
