This a sample 2G test suite configured and ready to use.
The only thing missing is a trial dir containing binaries.

You can point osmo-gsm-tester.py at this config using the '-c $DIR' command line
argument, where DIR is the directory path where this README file resides.

If you have your trial with binary tar archives in ~/my_trial
you can run the suite for example like this:
```
osmo-gsm-tester.py -c $DIR ~/my_trial
```

Alternatively you can setup this example as default config for your user by
doing something like:
```
mkdir -p ~/.config
ln -s "$DIR" ~/.config/osmo-gsm-tester
```

A ./state dir will be created to store the current osmo-gsm-tester state. If
you prefer not to write to $DIR, set up an own configuration pointing at a
different path (see paths.conf: 'state_dir').
