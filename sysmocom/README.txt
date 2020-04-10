This a real gsm test suite configured and ready to use.
The only thing missing is a trial dir containing binaries.

You can point osmo-gsm-tester.py at this config using the OSMO_GSM_TESTER_CONF
environment variable:

    export OSMO_GSM_TESTER_CONF="$PWD"

When there is no OSMO_GSM_TESTER_CONF set, osmo-gsm-tester will instead look
for conf files in several locations like ~/.config/osmo-gsm-tester,
/usr/local/etc/osmo-gsm-tester, /etc/osmo-gsm-tester.

If you have your trial with binary tar archives in ~/my_trial
you can run the suite for example like this:

    osmo-gsm-tester.py ~/my_trial

Specifically, from this dir:

    OSMO_GSM_TESTER_CONF="$PWD" ../src/osmo-gsm-tester.py ~/my_trial

Alternatively you can setup this example as permanent config using something
like:

    mkdir -p ~/.config
    ln -s "$PWD" ~/.config/osmo-gsm-tester

A ./state dir will be created to store the current osmo-gsm-tester state. If
you prefer not to write to $PWD, set up an own configuration pointing at a
different path (see paths.conf: 'state_dir').
