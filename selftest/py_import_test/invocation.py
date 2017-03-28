#!/usr/bin/env python3

import support
import importlib.util

if hasattr(importlib.util, 'module_from_spec'):
	def run_test(path):
		print('py 3.5+')
		spec = importlib.util.spec_from_file_location("tests.script", path)
		spec.loader.exec_module( importlib.util.module_from_spec(spec) )
else:
	def run_test(path):
		print('py 3.4-')
		from importlib.machinery import SourceFileLoader
		SourceFileLoader("tests.script", path).load_module()

path = './subdir/script.py'

support.config = 'specifics'
run_test(path)

support.config = 'specifics2'
run_test(path)

