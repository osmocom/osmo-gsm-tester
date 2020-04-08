#!/bin/sh
set -x
for filename in "$@"; do
        /sbin/setcap cap_net_admin,cap_sys_admin+ep "$filename"
done
