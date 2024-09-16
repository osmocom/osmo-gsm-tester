#!/bin/sh
set -e -x
base="$PWD"
name="osmo-sgsn"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen --disable-uring
build_repo libosmo-abis ${SANITIZE_FLAGS} --disable-dahdi
build_repo libosmo-netif ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-sigtran ${SANITIZE_FLAGS}
build_repo osmo-ggsn ${SANITIZE_FLAGS}
build_repo osmo-hlr ${SANITIZE_FLAGS}
build_repo libasn1c ${SANITIZE_FLAGS}
build_repo osmo-iuh ${SANITIZE_FLAGS}
build_repo osmo-sgsn ${SANITIZE_FLAGS} --enable-iu

create_bin_tgz osmo-sgsn
