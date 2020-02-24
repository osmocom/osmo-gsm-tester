#!/bin/bash -e

netns="$1"
ifname="$2" # optional

if [ -f "/var/run/netns/${netns}" ]; then
    echo "netns $netns already exists"
else
    echo "Creating netns $netns"
    ip netns add "$netns"
fi

if [ "x$ifname" = "x" ]; then
    exit 0
fi

if [ -d "/sys/class/net/${ifname}" ]; then
    echo "Moving iface $ifname to netns $netns"
    ip link set $ifname netns $netns
else
    ip netns exec $netns ls "/sys/class/net/${ifname}" >/dev/null && echo "iface $ifname already in netns $netns"
fi
