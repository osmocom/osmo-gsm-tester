#!/bin/sh
set -e -x

base="$PWD"
name="open5gs"
git_url="${git_url:-https://github.com/open5gs}"
project_name="${project_name:-open5gs}"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo $project_name "main" $configure_opts

create_bin_tgz "open5gs-hssd open5gs-pcrfd open5gs-upfd open5gs-sgwud open5gs-smfd open5gs-sgwcd open5gs-mmed"
