#!/bin/sh
python3 ./lock_test_help.py long name &
sleep .2
echo "launched first, locked by: $(cat /tmp/lock_test)"
python3 ./lock_test_help.py shorter &
echo "launched second, locked by: $(cat /tmp/lock_test)"
sleep .4
echo "waited, locked by: $(cat /tmp/lock_test)"
sleep .5
echo "waited more, locked by: $(cat /tmp/lock_test)"
