# osmo_ms_driver: A cumululative distribution function class.
# Help to start processes over time.
#
# Copyright (C) 2018 by Holger Hans Peter Freyther
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from datetime import timedelta

class DistributionFunctionHandler(object):
    """
    The goal is to start n "mobile" processes. We like to see some
    conflicts (RACH bursts being ignored) but starting n processes
    at the same time is not a realistic model.
    We use the concept of cumulative distribution function here. On
    the x-axis we have time (maybe in steps of 10ms) and on the
    y-axis we have the percentage (from 0.0 to 1.0) of how many
    processes should run at the given time.
    """

    def __init__(self, step, duration, fun):
        self._step = step
        self._fun = fun
        self._x = 0.0
        self._y = self._fun(self._x)
        self._target = 1.0
        self._duration = duration

    def step_size(self):
        return self._step

    def set_target(self, scale):
        """
        Scale the percentage to the target value..
        """
        self._target = scale

    def is_done(self):
        return self._y >= 1.0

    def current_value(self):
        return self._y

    def current_scaled_value(self):
        return self._y * self._target

    def step_once(self):
        self._x = self._x + self._step.total_seconds()
        self._y = self._fun(self._x)

    def duration(self):
        return self._duration


def immediate(step_size=timedelta(milliseconds=20)):
    """
    Reaches 100% at the first step.
    """
    duration = timedelta(seconds=0)
    return DistributionFunctionHandler(step_size, duration, lambda x: 1)

def linear_with_slope(slope, duration, step_size=timedelta(milliseconds=20)):
    """
    Use the slope and step size you want
    """
    return DistributionFunctionHandler(step_size, duration, lambda x: slope*x)

def linear_with_duration(duration, step_size=timedelta(milliseconds=20)):
    """
    Linear progression that reaches 100% after duration.total_seconds()
    """
    slope = 1.0/duration.total_seconds()
    return linear_with_slope(slope, duration, step_size)

def _in_out(x):
    """
    Internal in/out function inspired by Qt
    """
    assert x <= 1.0
    # Needs to be between 0..1 and increase first
    if x < 0.5:
        return (x*x) * 2
    # deaccelerate now. in_out(0.5) == 0.5, in_out(1.0) == 1.0
    x = x * 2 - 1
    return -0.5 * (x*(x-2)- 1)

def ease_in_out_duration(duration, step_size=timedelta(milliseconds=20)):
    """
    Example invocation
    """
    scale = 1.0/duration.total_seconds()
    return DistributionFunctionHandler(step_size, duration,
                                        lambda x: _in_out(x*scale))


cdfs = {
    'immediate': lambda x,y: immediate(y),
    'linear': linear_with_duration,
    'ease_in_out': ease_in_out_duration,
}
