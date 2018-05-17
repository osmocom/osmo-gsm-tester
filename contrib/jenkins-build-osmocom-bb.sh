#!/bin/sh
set -e -x

base="$PWD"
name="osmocom-bb"
. "$(dirname "$0")/jenkins-build-common.sh"

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


create_bin_tgz "" "osmocon"
