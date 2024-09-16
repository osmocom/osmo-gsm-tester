#!/bin/sh
set -e -x
base="$PWD"
name="osmo-stp"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen --disable-uring
build_repo libosmo-abis ${SANITIZE_FLAGS} --disable-dahdi
build_repo libosmo-netif ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-sigtran ${SANITIZE_FLAGS}

create_bin_tgz osmo-stp
