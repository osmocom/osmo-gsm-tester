#!/bin/sh
set -e -x
base="$PWD"
name="osmo-trx"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo osmo-trx --enable-sanitize --without-sse

create_bin_tgz osmo-trx
