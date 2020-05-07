.PHONY: check update

check: set_pythonpath
	./all_tests.py

update:
	./all_tests.py -u

set_pythonpath:
	echo "export PYTHONPATH=\"$(PWD)/../src\"" > set_pythonpath

clean:
	@find . -name "*__pycache__" -type d -print0 | xargs -0 rm -rvf
	@find . -name "*test_work" -type d -print0 | xargs -0 rm -rvf
	@rm -fv ./set_pythonpath

# vim: noexpandtab tabstop=8 shiftwidth=8
