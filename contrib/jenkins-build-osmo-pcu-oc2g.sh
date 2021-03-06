#!/bin/sh
set -e -x

_poky_version="$POKY_OC2G_VERSION"
_poky_path="$POKY_OC2G_PATH"

[ -z "$_poky_version" ] && _poky_version="2.3.4"
[ -z "$_poky_path" ] && _poky_path="/opt/poky-oc2g/$_poky_version"

. "$_poky_path/environment-setup-cortexa15hf-neon-poky-linux-gnueabi"

# Cross-compilation: all installations need to be put in the sysmo SDK sysroot
export DESTDIR="$_poky_path/sysroots/cortexa15hf-neon-poky-linux-gnueabi"

base="$PWD"
name="osmo-pcu-oc2g"
prefix="/usr/local/jenkins-build/inst-$name"
prefix_real="$DESTDIR$prefix"
. "$(dirname "$0")/jenkins-build-common.sh"

prev_git_url="${git_url}"
git_url="https://gitlab.com/nrw_oc2g/"
have_repo "oc2g-fw" "nrw/oc2g"
git_url="${prev_git_url}"
L1_OC2G_HEADERS="$PWD/oc2g-fw/inc"

build_repo libosmocore --disable-pcsc --disable-libmnl --disable-doxygen --disable-gnutls --disable-detect-tls-gcc-arm-bug
build_repo osmo-pcu --disable-sysmocom-dsp -enable-oc2gbts-phy --with-oc2g="$L1_OC2G_HEADERS"

create_bin_tgz osmo-pcu
