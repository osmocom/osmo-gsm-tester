This directory contains a set of scripts and osmo-gsm-tester testsuites to run
osmo-ttcn3-hacks.git BTS_tests.ttcn (https://git.osmocom.org/osmo-ttcn3-hacks/tree/bts).

The idea is to set up automatically the following components:
TTCN3 <-> osmocon (osmocom-bb) <-> motorola C123 <-> RF network <-> BTS_TO_TEST <-> TTCN3 + osmo-bsc

* A jenkins job builds a docker image containing a built BTS_tests TTCN testsuite.
* Another jenkins job retrieves the artifacts from osmo-gsm-tester-build jobs
  plus one for required osmocon binary. This job then calls osmo-gsm-tester/ttcn3/jenkins-run.sh, which will:
** Pull the above mentioned docker image containing BTS_Tests.
** Start osmo-gsm-tester with OSMO_GSM_TESTER_OPTS=osmo-gsm-tester/ttcn3/paths.conf,
   that contains mostly same stuff as regular osmo-gsm-tester jobs, but with a
   different testsuite containing 1 test "ttcn3_bts_tests.py".
** The test "ttcn3_bts_tests.py" does the following:
*** Start and manage all osmocom required components to run BTS_Tests: osmo-bts, osmo-bsc, osmocon, etc.
*** Generate the BTS_Tests.cfg required by BTS_Tests from a template to adapt to dynamic bits set by osmo-gsm-tester.
*** Launch script osmo-gsm-tester/ttcn3/suites/ttcn3_bts_tests/scripts/run_ttcn3_docker.sh with parameters and wait for it to finish.
    This script will start and manage the lifecycle of the docker container running BTS_Tests

See OS#3155 for more information regarding this topic.
