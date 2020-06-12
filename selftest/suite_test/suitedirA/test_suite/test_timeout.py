from osmo_gsm_tester.testenv import *

timeout = int(tenv.config_test_specific()['timeout'])
print('starting test and waiting to receive Timeout after %d seconds' % timeout)
sleep(10)
print('test failed, we expected timeout after %d seconds' % timeout)
