from osmo_gsm_tester.testenv import *
import pprint

print('starting test')

suite_config = tenv.config_suite_specific()
print('SPECIFIC SUITE CONFIG: ' + pprint.pformat(suite_config))

test_config = tenv.config_test_specific()
print('SPECIFIC TEST CONFIG: ' + pprint.pformat(test_config))

some_suite_global_param = suite_config.get('some_suite_global_param', '')
assert some_suite_global_param == 'heyho'

assert suite_config[tenv.test().module_name()] == test_config

one_bool_parameter = test_config.get('one_bool_parameter', '')
assert one_bool_parameter == 'true'

second_list_parameter = test_config.get('second_list_parameter', [])
assert len(second_list_parameter) == 2
assert int(second_list_parameter[0]) == 23
assert int(second_list_parameter[1]) == 45

#print('checks successful')
