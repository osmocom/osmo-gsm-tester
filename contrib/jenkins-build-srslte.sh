#!/bin/sh
set -e -x

base="$PWD"
name="srslte"
git_url="${git_url-"https://github.com/pespin/"}"
. "$(dirname "$0")/jenkins-build-common.sh"

#TODO: make sure libconfig, zeroMQ is installed
build_repo srsLTE

create_bin_tgz "srsue srsenb srsepc"
