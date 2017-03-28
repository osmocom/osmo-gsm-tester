.PHONY: check update

check: set_pythonpath
	./all_tests.py

update:
	./all_tests.py -u

set_pythonpath:
	echo "export PYTHONPATH=\"$(PWD)/../src\"" > set_pythonpath

# vim: noexpandtab tabstop=8 shiftwidth=8
