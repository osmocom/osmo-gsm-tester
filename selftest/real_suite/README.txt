This a real gsm test suite configured and ready to use.
The only thing missing is a trial dir containing binaries.

If you have your trial with binary tar archives in ~/my_trial
you can run the suite for example like this:

    . ./env  # point your environment at all the right places
    run_once.py ~/my_trial -s sms:trx

This combines the suites/sms test suite with the scenarios/trx choice of
osmo-bts-trx and runs all tests in the 'sms' suite.

A ./state dir will be created to store the current osmo-gsm-tester state. If
you prefer not to write to this dir, set up an own configuration pointing at a
different path (see paths.conf: 'state_dir' and the env file).  When there is
no OSMO_GSM_TESTER_CONF set (from ./env), osmo-gsm-tester will instead look for
conf files in several locations like ~/.config/osmo-gsm-tester,
/usr/local/etc/osmo-gsm-tester, /etc/osmo-gsm-tester
