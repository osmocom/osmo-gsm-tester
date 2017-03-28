#!/usr/bin/env python3

# just import all python3 modules used by osmo-gsm-tester to make sure they are
# installed.

from inspect import getframeinfo, stack
from mako.lookup import TemplateLookup
from mako.template import Template
import argparse
import contextlib
import copy
import difflib
import fcntl
import inspect
import io
import os
import pprint
import re
import subprocess
import sys
import tempfile
import time
import traceback
import yaml
import pydbus

print('dependencies ok')
