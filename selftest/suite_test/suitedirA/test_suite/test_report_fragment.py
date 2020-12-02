from osmo_gsm_tester.testenv import *

with test.report_fragment('fragment1'):
    print('a step in the first fragment')

with test.report_fragment('fragment2'):
    print('a step in the second fragment')

with test.report_fragment('fragment3'):
    print('a step in the third fragment')
    raise Exception('failure in the third fragment')
