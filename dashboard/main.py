#!/usr/bin/env python

import glob
import os
import re

import msgpack
import numpy as np

from bokeh.events import DoubleTap, SelectionGeometry
from bokeh.io import curdoc
from bokeh.layouts import row
from bokeh.models import CustomJS, Select
from bokeh.models.widgets.markups import Div
from bokeh.palettes import Spectral11
from pathlib import Path

from extremes import topouts, combined_topouts
from extremes import intervals_mask, filter_airtimes, filter_idlings
from extremes import add_airtime_labels, add_idling_marks
from fft import fft_figure, update_fft
from leverage import shock_wheel_figure, leverage_ratio_figure
from psst import Telemetry, dataclass_from_dict
from travel import travel_figure, travel_histogram_figure, update_travel_histogram
from velocity import velocity_histogram_figure, velocity_band_stats_figure
from velocity import update_velocity_band_stats, update_velocity_histogram


DATA_DIR = '/home/sghctoma/projects/sst/gosst/data/'

args = curdoc().session_context.request.arguments

psst_files = glob.glob(DATA_DIR + '/*.PSST')
psst_files.sort(key=os.path.getmtime)
psst_files = [Path(p).name for p in psst_files]
if not psst_files:
    curdoc().add_root(Div(text=f"Data directory does not contain PSST files!"))
    raise Exception("Empty data directory")

a = args.get('psst')
p = Path(a[0].decode('utf-8')).name if a else psst_files[-1]
psst_file = Path(DATA_DIR).joinpath(p)
if not psst_file.exists():
    curdoc().add_root(Div(text=f"File not found in data directory: {p}"))
    raise Exception("No such file")
d = msgpack.unpackb(open(psst_file, 'rb').read())

telemetry = dataclass_from_dict(Telemetry, d)

# lod - Level of Detail for travel graph (downsample ratio)
try:
    lod = int(args.get('lod')[0])
except:
    lod = 5

# hst - High Speed Threshold for velocity graphs/statistics in mm/s
try:
    hst = int(args.get('hst')[0])
except:
    hst = 100

tick = 1.0 / telemetry.SampleRate # time step length in seconds

front_travel, rear_travel = [], []
front_velocity, rear_velocity = [], []
front_topouts, rear_topouts = [], []
front_color, rear_color = Spectral11[1], Spectral11[2]
front_record_num, rear_record_num, record_num = 0, 0, 0

'''
Topouts are intervals where suspension is at zero extension for an extended period of time. It allows us to filter
out e.g. the beginning and the end of the ride, where the bike is at rest, or intervals where we stop mid-ride.
Filtering these out is important, because they can skew travel and velocity statistics. They are handled
individually for front and rear suspension.
'''
if telemetry.Front.Present:
    front_travel = np.array(telemetry.Front.Travel)
    front_record_num = len(front_travel)
    front_velocity = np.array(telemetry.Front.Velocity)
    front_topouts = topouts(front_travel, telemetry.Front.Calibration.MaxStroke, telemetry.SampleRate)
    front_topouts_mask = intervals_mask(front_topouts, front_record_num)

    if np.count_nonzero(front_topouts_mask):
        p_front_travel_hist = travel_histogram_figure(telemetry.Front.DigitizedTravel, front_travel, front_topouts_mask,
            front_color, "Travel histogram (front)")
        p_front_vel_hist = velocity_histogram_figure(telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
            front_velocity, front_topouts_mask, hst, "Speed histogram (front)")
        p_front_vel_stats = velocity_band_stats_figure(front_velocity[front_topouts_mask], hst)
        p_front_fft = fft_figure(front_travel[front_topouts_mask], tick, front_color, "Frequencies (front)")
    else:
        telemetry.Front.Present = False

if telemetry.Rear.Present:
    rear_travel = np.array(telemetry.Rear.Travel)
    rear_record_num = len(rear_travel)
    rear_velocity = np.array(telemetry.Rear.Velocity)
    rear_topouts = topouts(rear_travel, telemetry.Linkage.MaxRearTravel, telemetry.SampleRate)
    rear_topouts_mask = intervals_mask(rear_topouts, rear_record_num)

    if np.count_nonzero(rear_topouts_mask):
        p_rear_travel_hist = travel_histogram_figure(telemetry.Rear.DigitizedTravel, rear_travel, rear_topouts_mask,
            rear_color, "Travel histogram (rear)")
        p_rear_vel_hist = velocity_histogram_figure(telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
            rear_velocity, rear_topouts_mask, hst, "Speed histogram (rear)")
        p_rear_vel_stats = velocity_band_stats_figure(rear_velocity[rear_topouts_mask], hst)
        p_rear_fft = fft_figure(rear_travel[rear_topouts_mask], tick, rear_color, "Frequencies (rear)")
    else:
        telemetry.Rear.Present = False

if not (front_record_num == 0 or rear_record_num == 0) and front_record_num != rear_record_num:
    curdoc().add_root(Div(text=f"SST file is corrupt"))
    raise Exception("Corrupt dataset")

record_num = front_record_num if front_record_num else rear_record_num

'''
Event handlers for travel graph. We update histograms, statistics and FFTs when a selection is made with the Box Select
tool, and when the selection is cancelled with a double tap.
'''
def on_selectiongeometry(event):
    start = int(event.geometry['x0'] * telemetry.SampleRate)
    end = int(event.geometry['x1'] * telemetry.SampleRate)
    mask = np.full(record_num, False)
    mask[start:end] = True

    if telemetry.Front.Present:
        f_mask = front_topouts_mask & mask
        if np.count_nonzero(f_mask):
            update_travel_histogram(p_front_travel_hist, front_travel, telemetry.Front.DigitizedTravel, f_mask)
            update_fft(p_front_fft, front_travel[f_mask], tick)
            update_velocity_histogram(p_front_vel_hist, telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
                front_velocity, f_mask)
            update_velocity_band_stats(p_front_vel_stats, front_velocity[f_mask], hst)

    if telemetry.Rear.Present:
        r_mask = rear_topouts_mask & mask
        if np.count_nonzero(r_mask):
            update_travel_histogram(p_rear_travel_hist, rear_travel, telemetry.Rear.DigitizedTravel, r_mask)
            update_fft(p_rear_fft, rear_travel[r_mask], tick)
            update_velocity_histogram(p_rear_vel_hist, telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
                rear_velocity, r_mask)
            update_velocity_band_stats(p_rear_vel_stats, rear_velocity[r_mask], hst)

def on_doubletap():
    if telemetry.Front.Present:
        update_travel_histogram(p_front_travel_hist, front_travel, telemetry.Front.DigitizedTravel, front_topouts_mask)
        update_fft(p_front_fft, front_travel[front_topouts_mask], tick)
        update_velocity_histogram(p_front_vel_hist, telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
            front_velocity, front_topouts_mask)
        update_velocity_band_stats(p_front_vel_stats, front_velocity[front_topouts_mask], hst)

    if telemetry.Rear.Present:
        update_travel_histogram(p_rear_travel_hist, rear_travel, telemetry.Rear.DigitizedTravel, rear_topouts_mask)
        update_fft(p_rear_fft, rear_travel[rear_topouts_mask], tick)
        update_velocity_histogram(p_rear_vel_hist, telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
            rear_velocity, rear_topouts_mask)
        update_velocity_band_stats(p_rear_vel_stats, rear_velocity[rear_topouts_mask], hst)

p_travel = travel_figure(telemetry, lod, front_color, rear_color)
p_travel.on_event(SelectionGeometry, on_selectiongeometry)
p_travel.on_event(DoubleTap, on_doubletap)

'''
We use both suspensions to find airtimes. Basically, everything is considered airtime if both suspensions are close
to zero travel, and suspension velocity at the end of the interval reaches a threshold. A few remarks:
    - Originally, I used a velocity threshold at the beginning too of a candidate interval, but there were a lot of
    false negatives usually with drops.
    - We use the mean of front and rear travel to determine closeness to zero. This is based on the empirical
    observation that sometimes one of the suspensions (usually my fork) oscillates outside the set threshold during
    airtime (usually during drops). I expect this to become a problem if anybody else starts using this program, but
    could not come up with better heuristics so far.
'''
comb_topouts = combined_topouts(front_travel if telemetry.Front.Present else np.full(record_num, 0),
    telemetry.Front.Calibration.MaxStroke,
    rear_travel if telemetry.Rear.Present else np.full(record_num, 0),
    telemetry.Linkage.MaxRearTravel,
    telemetry.SampleRate)
airtimes = filter_airtimes(comb_topouts,
    front_velocity if telemetry.Front.Present else np.full(record_num, 0),
    rear_velocity if telemetry.Rear.Present else np.full(record_num, 0),
    telemetry.SampleRate)
airtimes_mask = intervals_mask(np.array(airtimes), record_num, False)
add_airtime_labels(airtimes, tick, p_travel)

'''
Mask out intervals on the travel graph that are ignored in statistics.
'''
if telemetry.Front.Present:
    front_idlings = filter_idlings(front_topouts, airtimes_mask)
    add_idling_marks(front_idlings, tick, p_travel)

if telemetry.Rear.Present:
    rear_idlings = filter_idlings(rear_topouts, airtimes_mask)
    add_idling_marks(rear_idlings, tick, p_travel)

'''
Leverage-related graphs. These are input data, not measured by this project.
'''
p_lr = leverage_ratio_figure(np.array(telemetry.Linkage.LeverageRatio), Spectral11[5])
p_sw = shock_wheel_figure(telemetry.Linkage.ShockWheelCoeffs, telemetry.Rear.Calibration.MaxStroke, Spectral11[5])

'''
Dropdown box to select PSST file
'''
select = Select(name='pssts_files', options=psst_files, value=psst_file.name)
select.js_on_change('value', CustomJS(code="window.location.replace('dashboard?psst=' + this.value)"))


'''
Disable tools for mobile browsers to allow scrolling
'''
def disable_tools(p):
    p.toolbar.active_drag = None
    p.toolbar.active_scroll = None
    p.toolbar.active_inspect= None

ua = ''
try:
    ua = curdoc().session_context.request.headers['User-Agent']
except:
    pass
if re.search('Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini', ua) is not None:
    disable_tools(p_travel)
    disable_tools(p_lr)
    disable_tools(p_sw)
    if telemetry.Front.Present:
        disable_tools(p_front_travel_hist)
        disable_tools(p_front_fft)
        disable_tools(p_front_vel_hist)
        disable_tools(p_front_vel_stats)
    if telemetry.Rear.Present:
        disable_tools(p_rear_travel_hist)
        disable_tools(p_rear_fft)
        disable_tools(p_rear_vel_hist)
        disable_tools(p_rear_vel_stats)

'''
Construct the layout.
'''
only_one_present = telemetry.Front.Present != telemetry.Rear.Present

curdoc().theme = 'dark_minimal'
curdoc().title = f"Sufni Suspension Telemetry Dashboard ({p})"
curdoc().template_variables["only_one"] =  only_one_present
curdoc().add_root(p_travel)
if telemetry.Front.Present:
    p_front_travel_hist.name = 'travel_hist' if only_one_present else 'front_travel_hist'
    p_front_fft.name = 'fft' if only_one_present else 'front_fft'
    p_front_velocity = row(name='velocity_hist' if only_one_present else 'front_velocity_hist',
        sizing_mode='stretch_width', children=[p_front_vel_hist, p_front_vel_stats])
    curdoc().add_root(p_front_travel_hist)
    curdoc().add_root(p_front_fft)
    curdoc().add_root(p_front_velocity)
if telemetry.Rear.Present:
    p_rear_travel_hist.name = 'travel_hist' if only_one_present else 'rear_travel_hist'
    p_rear_fft.name = 'fft' if only_one_present else 'rear_fft'
    p_rear_velocity = row(name='velocity_hist' if only_one_present else 'rear_velocity_hist',
        sizing_mode='stretch_width', children=[p_rear_vel_hist, p_rear_vel_stats])
    curdoc().add_root(p_rear_travel_hist)
    curdoc().add_root(p_rear_fft)
    curdoc().add_root(p_rear_velocity)
curdoc().add_root(p_lr)
curdoc().add_root(p_sw)
curdoc().add_root(select)
