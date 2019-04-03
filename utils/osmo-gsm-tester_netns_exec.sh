#!/bin/bash
netns="$1"
shift

child_ps=0
forward_kill() {
	sig="$1"
	echo "Caught signal SIG$sig!"
	if [ "$child_ps" != "0" ]; then
		echo "Killing $child_ps with SIG$sig!"
		kill -SIG${sig} $child_ps
	else
		exit 0
	fi
}
forward_kill_int() {
	forward_kill "INT"
}
forward_kill_term() {
	forward_kill "TERM"
}
forward_kill_usr1() {
	# Special signal received from osmo-gsm-tester to tell child to SIGKILL
	echo "Converting SIGUSR1->SIGKILL"
	forward_kill "KILL"
}
# Don't use 'set -e', otherwise traps are not triggered!
trap forward_kill_int INT
trap forward_kill_term TERM
trap forward_kill_usr1 USR1

#TODO: Later on I may want to call myself with specific ENV and calling sudo in order to run inside the netns but with dropped privileges
ip netns exec $netns "$@" &
child_ps=$!

echo "$$: waiting for $child_ps"
wait "$child_ps"
child_exit_code="$?"
echo "child exited with $child_exit_code"

exit $child_exit_code
