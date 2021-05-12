#!/bin/bash -e

ifname="$1"
ifaddr="$2"
ifmask="$3"

echo "*** Configuring tun $ifname with addr $ifaddr/$ifmask"

if grep "$ifname" /proc/net/dev > /dev/null; then
        ip tuntap del name "$ifname" mode tun
fi

ip tuntap add name "$ifname" mode tun

ip addr add "$ifaddr/$ifmask" dev "$ifname"
ip link set "$ifname" up
echo "*** done configuring tun interface $ifname"
