#!/bin/sh
set -e -x

base="$PWD"
name="osmocom-bb"
. "$(dirname "$0")/jenkins-build-common.sh"

FW_RPM_URL="http://download.opensuse.org/repositories/home:/mnhauke:/osmocom:/nightly/SLE_15/x86_64/"

build_repo libosmocore --disable-doxygen

have_repo osmocom-bb
cd osmocom-bb/

cd src/host/osmocon/
set +x; echo; echo; set -x
autoreconf -fi
set +x; echo; echo; set -x
./configure --prefix="$prefix" $CONFIGURE_FLAGS $configure_opts
set +x; echo; echo; set -x
make -j4
set +x; echo; echo; set -x
make install

mkdir -p "$prefix"
cd "$prefix"
FW_RPM="$(wget -q -O - "$FW_RPM_URL" | grep -o 'osmocom-bb-firmware.*rpm' | sed 's#\"#\n#g' | head -1)"
echo "Downloading RPM package $FW_RPM"
wget -q "$FW_RPM_URL/$FW_RPM" -O osmocom-bb-firmware.rpm
rpm2cpio osmocom-bb-firmware.rpm  | cpio -idmv
rm osmocom-bb-firmware.rpm

create_bin_tgz "" "osmocon"
