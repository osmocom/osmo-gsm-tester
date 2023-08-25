#!/bin/sh
set -e -x
base="$PWD"
name="osmo-ggsn"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen --disable-uring
build_repo osmo-ggsn ${SANITIZE_FLAGS}

create_bin_tgz osmo-ggsn
