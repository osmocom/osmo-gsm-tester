#!/bin/sh
set -e -x
base="$PWD"
name="osmo-bts"
. "$(dirname "$0")/jenkins-build-common.sh"

(git_url=https://gitea.osmocom.org/cellular-infrastructure
 have_repo octphy-2g-headers)

build_repo libosmocore ${SANITIZE_FLAGS} --disable-doxygen --disable-uring
build_repo libosmo-abis ${SANITIZE_FLAGS} --disable-dahdi
build_repo libosmo-netif ${SANITIZE_FLAGS} --disable-doxygen
build_repo osmo-bts ${SANITIZE_FLAGS} --enable-trx --with-openbsc=$base/openbsc/openbsc/include --enable-octphy --with-octsdr-2g=$base/octphy-2g-headers

create_bin_tgz "osmo-bts-trx osmo-bts-octphy osmo-bts-virtual"
