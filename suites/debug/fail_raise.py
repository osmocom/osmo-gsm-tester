#!/usr/bin/env python3
from osmo_gsm_tester.test import *

class ExpectedExn(Exception):
    pass

# This can be used to verify that a test failure is reported properly.
raise ExpectedExn('This failure is expected')
