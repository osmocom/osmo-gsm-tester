#!/bin/sh
set -e -x
base="$PWD"
name="osmo-ggsn"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo osmo-ggsn --enable-sanitize

create_bin_tgz osmo-ggsn
