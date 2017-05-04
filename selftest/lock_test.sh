#!/bin/sh
dir="$(mktemp -d)"
n1="long name"
f1="$dir/$n1"
touch "$f1"
n2="shorter"
f2="$dir/$n2"
touch "$f2"
sync
python3 ./lock_test_help.py "$dir" "$n1" &
while [ ! -f "$dir/lock_test" ]; do
  sleep .1
done
echo "launched first, locked by: $(cat "$dir/lock_test")"
python3 ./lock_test_help.py "$dir" "$n2" &
echo "launched second, locked by: $(cat "$dir/lock_test")"
rm "$f1"
while [ ! -f "$f1.done" ]; do
  sleep .1
done
echo "waited, locked by: $(cat "$dir/lock_test")"
rm "$f2"
while [ ! -f "$f2.done" ]; do
  sleep .1
done
echo "waited more, locked by: $(cat "$dir/lock_test")"
rm -rf "$dir"
