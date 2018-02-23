#!/bin/sh
set -e -x
base="$PWD"
name="osmo-trx"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen
build_repo osmo-trx --without-sse

create_bin_tgz osmo-trx
