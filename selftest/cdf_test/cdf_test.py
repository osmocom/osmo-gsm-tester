#!/usr/bin/env python3

import _prep

from osmo_ms_driver import cdf
from datetime import timedelta

def print_fuzzy_compare(want, expe, len=3):
    want_str = str(want)[0:len]
    expe_str = str(expe)[0:len]
    print(want_str, expe_str, want_str == expe_str)


def check_steps(a, steps, fun):
    print("Done", a.is_done())
    for step in steps:
        # Verify we can step

        # Compare and step once
        fun(a, step)
        if a.is_done():
            break
        a.step_once()
        print("Done", a.is_done())

def compare_value(a, step):
    print_fuzzy_compare(a.current_value(), step)

def compare_scaled_value(a, val):
    (step, scale) = val
    print_fuzzy_compare(a.current_value(), step)
    print_fuzzy_compare(a.current_scaled_value(), scale)

def compare_x_value(a, val):
    (x, step) = val
    print(a._x, x, x == a._x)
    print_fuzzy_compare(a.current_value(), step)

def testImmediate():
    print("Testing the immediate CDF")
    a = cdf.immediate()
    print("Done", a.is_done())
    print_fuzzy_compare(a.current_value(), 1.0)


def testLinearWithDuration():
    print("Testing linear with duration")
    a = cdf.linear_with_duration(timedelta(seconds=10), step_size=timedelta(seconds=2))
    steps = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    check_steps(a, steps, compare_value)

    print("Testing linear with duration scaled")
    a = cdf.linear_with_duration(timedelta(seconds=10), step_size=timedelta(seconds=2))
    a.set_target(1000)
    steps = [(0.0, 0.0), (0.2, 200), (0.4, 400), (0.6, 600), (0.8, 800), (1.0, 10000)]
    check_steps(a, steps, compare_scaled_value)

def testInOut():
    print("Testing in_out")
    print_fuzzy_compare(cdf._in_out(0.5), 0.5, 3)
    print_fuzzy_compare(cdf._in_out(0.75), 0.875, 4)
    print_fuzzy_compare(cdf._in_out(0.8), 0.92, 3)
    print_fuzzy_compare(cdf._in_out(0.85), 0.955, 4)
    print_fuzzy_compare(cdf._in_out(1.0), 1.0, 3)

def testEaseInOutDuration():
    print("Testing ease In and Out")
    a = cdf.ease_in_out_duration(duration=timedelta(seconds=20), step_size=timedelta(seconds=5))
    steps = [(0.0, 0.0), (5.0, 0.125), (10.0, 0.5), (15.0, 0.875), (20, 1.0)]
    check_steps(a, steps, compare_x_value)

testImmediate()
testLinearWithDuration()
testInOut()
testEaseInOutDuration()
