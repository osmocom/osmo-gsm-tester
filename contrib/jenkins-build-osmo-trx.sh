#!/bin/sh
set -e -x
base="$PWD"
name="osmo-trx"
. "$(dirname "$0")/jenkins-build-common.sh"

# AddressSanitizer is not enabled on purpose since overhead affects the clocking.
build_repo libosmocore --disable-doxygen
build_repo osmo-trx --without-sse --with-uhd

create_bin_tgz osmo-trx-uhd
