#!/bin/sh
set -x

RUNDIR="$1"
JUNIT_TTCN3_DST_FILE="$2"
L2_SOCKET_PATH="$3"
PCU_SOCKET_PATH="$4"

# Absolute path to this script
SCRIPT=$(readlink -f "$0")
# Absolute path this script is in
SCRIPTPATH=$(dirname "$SCRIPT")

VOL_BASE_DIR="$RUNDIR/logs"
rm -rf "$VOL_BASE_DIR"
mkdir -p "$VOL_BASE_DIR"

if [ "x$BUILD_TAG" = "x" ]; then
	BUILD_TAG=nonjenkins
fi

REPO_USER="registry.sysmocom.de"
SUITE_NAME="ttcn3-bts-test"
NET_NAME=$SUITE_NAME
DOCKER_NAME="$BUILD_TAG-$SUITE_NAME"

network_create() {
	NET=$1
	echo Creating network $NET_NAME
	docker network create --internal --subnet $NET $NET_NAME
}

network_remove() {
	echo Removing network $NET_NAME
	docker network remove $NET_NAME
}

child_ps=0
forward_kill() {
	sig="$1"
	echo "Caught signal SIG$sig!"
	if [ "$child_ps" != "0" ]; then
		echo "Killing $child_ps with SIG$sig!"
		docker kill ${DOCKER_NAME}
	fi
	exit 130
}
forward_kill_int() {
	forward_kill "INT"
}
forward_kill_term() {
	forward_kill "TERM"
}
# Don't use 'set -e', otherwise traps are not triggered!
trap forward_kill_int INT
trap forward_kill_term TERM

network_create 172.18.9.0/24

mkdir $VOL_BASE_DIR/bts-tester
echo "SCRIPTPATH=$SCRIPTPATH PWD=$PWD"
cp $RUNDIR/BTS_Tests.cfg $VOL_BASE_DIR/bts-tester/

echo Starting container with BTS testsuite
docker kill ${DOCKER_NAME}
docker run	--rm \
		--network $NET_NAME --ip 172.18.9.10 \
		-e "TTCN3_PCAP_PATH=/data" \
		--mount type=bind,source=$VOL_BASE_DIR/bts-tester,destination=/data \
		--mount type=bind,source="$(dirname "$L2_SOCKET_PATH")",destination=/data/unix_l2 \
		--mount type=bind,source="$(dirname "$PCU_SOCKET_PATH")",destination=/data/unix_pcu \
		--name ${DOCKER_NAME} \
		$REPO_USER/${SUITE_NAME} &
child_ps=$!
echo "$$: waiting for $child_ps"
wait "$child_ps"
child_exit_code="$?"
echo "ttcn3 docker exited with code $child_exit_code"

network_remove

echo "Copying TTCN3 junit file to $JUNIT_TTCN3_DST_FILE"
cp $VOL_BASE_DIR/bts-tester/junit-xml-*.log $JUNIT_TTCN3_DST_FILE
sed -i "s#classname='BTS_Tests'#classname='$(basename $JUNIT_TTCN3_DST_FILE)'#g" $JUNIT_TTCN3_DST_FILE

exit $child_exit_code
