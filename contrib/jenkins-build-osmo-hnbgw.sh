#!/bin/sh
set -e -x
base="$PWD"
name="osmo-hnbgw"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-abis ${SANITIZE_FLAGS} --disable-dahdi
build_repo libosmo-netif ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-sccp ${SANITIZE_FLAGS}
build_repo libasn1c ${SANITIZE_FLAGS}
build_repo osmo-iuh ${SANITIZE_FLAGS}
build_repo osmo-mgw ${SANITIZE_FLAGS}

build_repo osmo-hnbgw ${SANITIZE_FLAGS}

create_bin_tgz "osmo-hnbgw"
