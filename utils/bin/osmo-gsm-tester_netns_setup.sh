#!/bin/bash -e

netns="$1"
ifname="$2" # optional
ip_addr="$3" # optional

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

if [ "x$ip_addr" = "x" ]; then
    exit 0
fi

echo "Setting up iface $ifname with ${ip_addr}"
ip netns exec $netns ip link set dev $ifname up
ip netns exec $netns ip addr add ${ip_addr}/24 dev $ifname

#ip netns exec $netns ip route add default via ${ip_addr}
