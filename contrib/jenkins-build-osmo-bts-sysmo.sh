#!/bin/sh
set -e -x

poky="/opt/poky/1.5.4"
. "$poky/environment-setup-armv5te-poky-linux-gnueabi"

# Cross-compilation: all installations need to be put in the sysmo SDK sysroot
export DESTDIR="$poky/sysroots/armv5te-poky-linux-gnueabi"

base="$PWD"
name="osmo-bts-sysmo"
prefix="/usr/local/jenkins-build/inst-$name"
prefix_real="$DESTDIR$prefix"
. "$(dirname "$0")/jenkins-build-common.sh"

# for gsm_data_shared.h
have_repo openbsc

build_repo libosmocore --disable-pcsc --disable-doxygen
build_repo libosmo-abis
build_repo osmo-bts --enable-sysmocom-bts --with-openbsc=$base/openbsc/openbsc/include

create_bin_tgz
