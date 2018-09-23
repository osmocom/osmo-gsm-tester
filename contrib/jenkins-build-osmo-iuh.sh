#!/bin/sh
set -e -x
base="$PWD"
name="osmo-iuh"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-abis ${SANITIZE_FLAGS}
build_repo libosmo-netif ${SANITIZE_FLAGS} --disable-doxygen
build_repo libosmo-sccp ${SANITIZE_FLAGS}
build_repo libasn1c ${SANITIZE_FLAGS}

build_repo osmo-iuh ${SANITIZE_FLAGS}

create_bin_tgz "osmo-hnbgw"
