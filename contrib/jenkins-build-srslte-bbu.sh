#!/bin/sh
set -e -x

if [ -z "$trial_binaries" ]; then
  trial_binaries="srsue srsenb srsepc"
fi

export patchelf_rpath_dir="/mnt/nfs/bdlibs"
export patchelf_rapth_extra_args="--force-rpath"

base="$PWD"
name="srslte"
git_url="${git_url:-https://github.com/srsLTE}"
project_name="${project_name:-srsLTE}"
. "$(dirname "$0")/jenkins-build-common.sh"

#TODO: make sure libconfig, zeroMQ is installed
build_repo $project_name $configure_opts

create_bin_tgz "$trial_binaries"
