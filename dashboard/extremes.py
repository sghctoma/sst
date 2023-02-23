import numpy as np

from bokeh.models.annotations import BoxAnnotation, Label
from bokeh.palettes import Spectral11


def _get_intervals(data, threshold):
    x = np.r_[False, (data), False]
    start = np.r_[False, ~x[:-1] & x[1:]]
    end = np.r_[x[:-1] & ~x[1:], False]
    # creating start-end pairs while filtering out single <threshold values
    intervals = np.where(start ^ end)[0] - 1
    intervals.shape = (-1, 2)
    diff = intervals[:, -1] - intervals[:, 0]
    # return intervals longer than threshold
    return intervals[diff > threshold]


def topouts(travel, max_travel, sample_rate):
    travel_nz = travel < max_travel * 0.04
    # return topout intervals longer than 0.5s
    return _get_intervals(travel_nz, 0.5 * sample_rate)


def combined_topouts(front_travel, front_max,
                     rear_travel, rear_max, sample_rate):
    combined_mean = np.mean([front_travel, rear_travel], axis=0)
    combined_max_mean = (front_max + rear_max) / 2.0
    travel_nz = combined_mean < combined_max_mean * 0.04
    # return topout intervals longer than 0.2s
    return _get_intervals(travel_nz, 0.2 * sample_rate)


def intervals_mask(intervals, length, invert=True):
    if intervals.size == 0:
        return np.full(length, invert)
    r = np.arange(length)
    l0 = intervals[:, [0]] <= r
    l1 = intervals[:, [1]] > r
    return (np.logical_not(np.any(l0 & l1, axis=0)) if invert else
            np.any(l0 & l1, axis=0))


def filter_airtimes(topouts, front_velocity, rear_velocity, sample_rate):
    airtimes = []
    if len(topouts) == 0:
        return airtimes
    v_check_interval = int(0.02 * sample_rate)

    # beginning is not airtime
    if topouts[0][0] < v_check_interval:
        # !!! This might empty out topouts, so we need to check.
        topouts = topouts[1:]
    # end is not airtime
    if len(topouts) and topouts[-1][1] > len(front_velocity) - v_check_interval:
        topouts = topouts[:-1]

    for to in topouts:
        v_front_after = np.mean(front_velocity[to[1]:to[1] + v_check_interval])
        v_rear_after = np.mean(rear_velocity[to[1]:to[1] + v_check_interval])
        # if suspension speed on landing is sufficiently large
        if v_front_after > 500 or v_rear_after > 500:
            airtimes.append(to)
    return airtimes


def add_airtime_labels(airtime, tick, p_travel):
    for j in airtime:
        t1 = j[0] * tick
        t2 = j[1] * tick
        b = BoxAnnotation(left=t1, right=t2,
                          fill_color=Spectral11[-2], fill_alpha=0.2)
        p_travel.add_layout(b)
        l = Label(
            x=t1 + (t2 - t1) / 2,
            y=30,
            x_units='data',
            y_units='screen',
            text_font_size='14px',
            text_color='#fefefe',
            text_align='center',
            text_baseline='middle',
            text=f"{t2-t1:.2f}s air")
        p_travel.add_layout(l)


def filter_idlings(topouts, mask):
    idlings = []
    for to in topouts:
        if not np.any(mask[to[0]:to[1]]):
            idlings.append(to)
    return idlings


def add_idling_marks(idlings, tick, p_travel):
    for i in idlings:
        t1 = i[0] * tick
        t2 = i[1] * tick
        p_travel.add_layout(BoxAnnotation(
            left=t1, right=t2, fill_color='black', fill_alpha=0.4))


def bottomouts(travel, max_travel):
    x = np.r_[False, (max_travel - travel < 3), False]
    bo_start = np.r_[False, ~x[:-1] & x[1:]]
    return bo_start.nonzero()[0]
