#!/usr/bin/env python3
# Alexander Couzens <lynxis@fe80.eu>
# MIT

# show usb device with their net and serial devices

import os
import usb.core
import usb.util
from pprint import pprint

def get_path_ids(bus, port_numbers):
    port_numbers = [str(port) for port in port_numbers]
    ports = '.'.join(port_numbers)
    return '{}-{}'.format(bus, ports)

def get_usb_dir(bus, port_numbers):
    return '/sys/bus/usb/devices/' + get_path_ids(bus, port_numbers) + '/'

def get_usbmisc_from_usb(bus, port_numbers):
    usbmisc_ifaces = []
    path = get_usb_dir(bus, port_numbers)
    path_ids = get_path_ids(bus, port_numbers)

    usb_interfaces = [f for f in os.listdir(path) if f.startswith(path_ids)]
    for usb_iface in usb_interfaces:
        listdir = [f for f in os.listdir(path + usb_iface) if f == ('usbmisc')]
        if listdir:
            # found a net iface
            usbmisc_ifaces += os.listdir(path + usb_iface + '/usbmisc/')
    return usbmisc_ifaces

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

def get_serial_from_usb(bus, port_numbers):
    serial_ifaces = []
    path = get_usb_dir(bus, port_numbers)
    path_ids = get_path_ids(bus, port_numbers)

    usb_interfaces = [f for f in os.listdir(path) if f.startswith(path_ids)]
    for usb_iface in usb_interfaces:
        serial_ifaces += [f for f in os.listdir(path + usb_iface) if f.startswith('tty')]
    return serial_ifaces

def get_product(bus, port_numbers):
    usb_dir = get_usb_dir(bus, port_numbers)
    try:
        product = open(os.path.join(usb_dir, 'product')).read().strip()
    except OSError as exp:
        product = "Unknown"
    return product

def get_manuf(bus, port_numbers):
    usb_dir = get_usb_dir(bus, port_numbers)
    try:
        manuf = open(os.path.join(usb_dir, 'manufacturer')).read().strip()
    except OSError:
        manuf = "Unknown"
    return manuf

def get_name(bus, port_numbers):
    manuf = get_manuf(bus, port_numbers)
    product = get_product(bus, port_numbers)
    return "%s %s" % (manuf, product)

if __name__ == '__main__':
    USB_DEVS = [dev for dev in usb.core.find(find_all=True)]
    RESULT = {}
    for device in USB_DEVS:
        result = {}
        if not device.port_numbers:
            continue

        # retrieve manuf + product from /sys because non-root user can not ask the usb device
        result['name'] = get_name(device.bus, device.port_numbers)
        result['path'] = get_usb_dir(device.bus, device.port_numbers)
        result['net'] = get_net_from_usb(device.bus, device.port_numbers)
        result['cdc'] = get_usbmisc_from_usb(device.bus, device.port_numbers)
        result['serial'] = get_serial_from_usb(device.bus, device.port_numbers)

        # only show device which have serial or net devices
        if result['net'] or result['serial']:
            RESULT[device] = result

    pprint(RESULT)

