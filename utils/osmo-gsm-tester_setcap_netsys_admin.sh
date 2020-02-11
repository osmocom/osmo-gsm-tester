#!/bin/sh
/sbin/setcap cap_net_admin,cap_sys_admin+ep "$1"
