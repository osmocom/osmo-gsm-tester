#!/bin/sh

echo 'creating files'
dir="$(mktemp -d)"
n1="long name"
f1="$dir/$n1"
touch "$f1"
n2="shorter"
f2="$dir/$n2"
touch "$f2"
sync

echo 'launch a program that locks a given file, it will create $dir/lock_test'
python3 ./lock_test_help.py "$dir" "$n1" &

echo 'wait until this lock_test lock file was created by program'
while [ ! -f "$dir/lock_test" ]; do
  sleep .1
done
sync

echo 'expecting the lock file to reflect "long name"'
echo "launched first, locked by: '$(cat "$dir/lock_test")'"

echo 'launching second program, should find the lock intact and wait'
python3 ./lock_test_help.py "$dir" "$n2" &
while [ ! -f "$f2.ready" ]; do
  sleep .1
done
sleep 1
sync
echo "launched second, locked by: '$(cat "$dir/lock_test")'"

echo 'drop the first lock, $f1 removal signals the first process to stop locking'
rm "$f1"

echo 'wait for first program to carry out the lock release'
while [ ! -f "$f1.done" ]; do
  sleep .1
done

echo 'now expecting second program to lock'
echo "waited, locked by: '$(cat "$dir/lock_test")'"

echo 'release the second program also'
rm "$f2"
while [ ! -f "$f2.done" ]; do
  sleep .1
done

echo 'expecting the lock to be gone'
echo "waited more, locked by: '$(cat "$dir/lock_test")'"
rm -rf "$dir"
