#!/bin/bash -e
ifname="$1"     # Interface name
index="$2"      # Network index (PDN index)
apn="$3"        # Access point name
type="$4"       # ipv4 or ipv6
ifaddr="$5" # Interface address
addr1="$6"  # First IP address
addr2="$7"  # Last IP address
mask="$8"   # Mask
echo "*** Configuring $type APN[$index] '$apn' on ${ifname}, $ifaddr/$mask, ${addr1}..${addr2}"
if [ "$type" = "ipv4" ] ; then
        ip addr add ${ifaddr}/${mask} dev ${ifname}
        ip link set ${ifname} up
else
        ip -6 addr add ${addr1}/${mask} dev ${ifname}
        ip -6 link set ${ifname} up
fi
echo "*** done configuring interface ${ifname}"
