#!/usr/bin/env python3
# Pau Espin Pedrol <pespin@sysmocom.de>
# MIT

# manage netns for ofono modems

import os
import sys
import subprocess
import usb.core
import usb.util
from pprint import pprint

def get_path_ids(bus, port_numbers):
    port_numbers = [str(port) for port in port_numbers]
    ports = '.'.join(port_numbers)
    return '{}-{}'.format(bus, ports)

def get_usb_dir(bus, port_numbers):
    return '/sys/bus/usb/devices/' + get_path_ids(bus, port_numbers) + '/'

def get_net_from_usb(bus, port_numbers):
    net_ifaces = []
    path = get_usb_dir(bus, port_numbers)
    path_ids = get_path_ids(bus, port_numbers)

    usb_interfaces = [f for f in os.listdir(path) if f.startswith(path_ids)]
    for usb_iface in usb_interfaces:
        listdir = [f for f in os.listdir(path + usb_iface) if f == ('net')]
        if listdir:
            # found a net iface
            net_ifaces += os.listdir(path + usb_iface + '/net/')
    return net_ifaces

def move_modem_to_netns(usb_path_id, net_li):

        if len(net_li) == 0:
            print("%s: Device has no net ifaces, skipping" %(usb_path_id))
            return

        if not os.path.exists("/var/run/netns/%s" % usb_path_id):
            print("%s: Creating netns" % (usb_path_id))
            subprocess.check_call(["ip", "netns", "add", usb_path_id])
        else:
            print("%s: netns already exists" % (usb_path_id))

        for netif in net_li:
            print("%s: Moving iface %s to netns" % (usb_path_id, netif))
            subprocess.check_call(["ip", "link", "set", netif, "netns", usb_path_id])
            # iface Must be set up AFTER pdp ctx is activated, otherwise we get no DHCP response.
            #print("%s: Setting up iface %s" % (usb_path_id, netif))
            #subprocess.check_call(["ip", "netns", "exec", usb_path_id, "ip", "link", "set", "dev", netif, "up"])
            #subprocess.check_call(["ip", "netns", "exec", usb_path_id, "udhcpc", "-i", netif])

def delete_modem_netns(usb_path_id):
        if os.path.exists("/var/run/netns/%s" % usb_path_id):
            print("%s: Deleting netns" % (usb_path_id))
            subprocess.check_call(["ip", "netns", "delete", usb_path_id])
        else:
            print("%s: netns doesn't exist" % (usb_path_id))

def print_help():
    print("Usage: %s start|stop" % sys.argv[0])
    exit(1)


if __name__ == '__main__':

    if len(sys.argv) != 2:
        print_help()

    USB_DEVS = [dev for dev in usb.core.find(find_all=True)]
    RESULT = {}
    for device in USB_DEVS:
        result = {}
        if not device.port_numbers:
            continue

        usb_path_id = get_path_ids(device.bus, device.port_numbers)
        net_li = get_net_from_usb(device.bus, device.port_numbers)

        if sys.argv[1] == "start":
            move_modem_to_netns(usb_path_id, net_li)
        elif sys.argv[1] == "stop":
            delete_modem_netns(usb_path_id)
        else:
            print_help()
