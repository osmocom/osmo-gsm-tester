#!/bin/sh
set -e -x
base="$PWD"
name="osmo-trx"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo_limesuite() {
set +x; echo "

====================== $dep

"; set -x

prev_git_url="${git_url}"
git_url="https://github.com/myriadrf/"
have_repo "LimeSuite" "master"
git_url="${prev_git_url}"
cd "LimeSuite"

set +x; echo; echo; set -x
mkdir -p builddir && cd builddir
set +x; echo; echo; set -x
cmake -DCMAKE_INSTALL_PREFIX:PATH=$prefix ../
set +x; echo; echo; set -x
make -j5
set +x; echo; echo; set -x
make install
}

# We want to use LimSuite installed by debian repos
# build_repo_limesuite

# AddressSanitizer is not enabled on purpose since overhead affects the clocking.
build_repo libosmocore --disable-doxygen
build_repo osmo-trx --with-uhd --with-lms

create_bin_tgz "osmo-trx-uhd osmo-trx-lms"
