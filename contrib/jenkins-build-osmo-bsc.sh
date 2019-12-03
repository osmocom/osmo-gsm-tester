#!/bin/sh
set -e -x
base="$PWD"
name="osmo-bsc"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-abis ${SANITIZE_FLAGS} --disable-dahdi
build_repo libosmo-netif ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-sccp ${SANITIZE_FLAGS}
build_repo osmo-mgw ${SANITIZE_FLAGS}
build_repo osmo-bsc ${SANITIZE_FLAGS}

create_bin_tgz "osmo-bsc abisip-find ipaccess-config"
