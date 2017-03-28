#!/usr/bin/env python3

msisdn = '0000'

l = len(msisdn)
next_msisdn = ('%%0%dd' % l) % (int(msisdn) + 1)
print(next_msisdn)
