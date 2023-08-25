#!/bin/sh
set -e -x
base="$PWD"
name="osmo-hlr"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen --disable-uring
build_repo libosmo-abis ${SANITIZE_FLAGS} --disable-dahdi
build_repo osmo-hlr ${SANITIZE_FLAGS}

create_bin_tgz osmo-hlr
