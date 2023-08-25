#!/bin/sh
set -e -x
base="$PWD"
name="osmo-pcu"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-pcsc --disable-doxygen --disable-uring
build_repo osmo-pcu ${SANITIZE_FLAGS}

create_bin_tgz osmo-pcu
