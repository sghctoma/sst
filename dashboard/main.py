#!/usr/bin/env python

import msgpack
import numpy as np

from bokeh.events import DoubleTap, SelectionGeometry
from bokeh.io import curdoc
from bokeh.layouts import column, layout
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


args = curdoc().session_context.request.arguments
p = Path(args.get('psst')[0].decode('utf-8')).name
psst_file = Path('data').joinpath(p)
telemetry = dataclass_from_dict(Telemetry, msgpack.unpackb(open(psst_file, 'rb').read()))

# lod - Level of Detail for travel graph (downsample ratio)
try:
    lod = int(args.get('lod')[0])
except:
    lod = 100

# hst - High Speed Threshold for velocity graphs/statistics in mm/s
try:
    hst = int(args.get('hst')[0])
except:
    hst = 100

tick = 1.0 / telemetry.SampleRate # time step length in seconds

# collect information for graphs
front_travel = np.array(telemetry.Front.Travel)
front_velocity = np.array(telemetry.Front.Velocity)
rear_travel = np.array(telemetry.Rear.Travel)
rear_velocity = np.array(telemetry.Rear.Velocity)

'''
Topouts are intervals where suspension is at zero extension for an extended period of time. It allows us to filter
out e.g. the beginning and the end of the ride, where the bike is at rest, or intervals where we stop mid-ride.
Filtering these out is important, because they can skew travel and velocity statistics. They are handled
individually for front and rear suspension.
'''
front_topouts = topouts(front_travel, telemetry.Front.Calibration.MaxStroke, telemetry.SampleRate)
rear_topouts = topouts(rear_travel, telemetry.Frame.MaxRearTravel, telemetry.SampleRate)
front_topouts_mask = intervals_mask(front_topouts, len(front_travel))
rear_topouts_mask = intervals_mask(rear_topouts, len(rear_travel))

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
comb_topouts = combined_topouts(front_travel, telemetry.Front.Calibration.MaxStroke,
    rear_travel, telemetry.Frame.MaxRearTravel, telemetry.SampleRate)
airtimes = filter_airtimes(comb_topouts, front_velocity, rear_velocity, telemetry.SampleRate)
airtimes_mask = intervals_mask(np.array(airtimes), len(front_travel), False)
front_idlings = filter_idlings(front_topouts, airtimes_mask)
rear_idlings = filter_idlings(rear_topouts, airtimes_mask)

# travel graph event handlers
def on_selectiongeometry(event):
    start = int(event.geometry['x0'] * telemetry.SampleRate)
    end = int(event.geometry['x1'] * telemetry.SampleRate)
    mask = np.full(len(telemetry.Front.Travel), False)
    mask[start:end] = True
    f_mask = front_topouts_mask & mask
    r_mask = rear_topouts_mask & mask

    update_travel_histogram(p_front_travel_hist, front_travel, telemetry.Front.DigitizedTravel, f_mask)
    update_travel_histogram(p_rear_travel_hist, rear_travel, telemetry.Rear.DigitizedTravel, r_mask)
    update_fft(p_front_fft, front_travel[f_mask], tick)
    update_fft(p_rear_fft, rear_travel[r_mask], tick)
    update_velocity_histogram(p_front_vel_hist, telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
        front_velocity, f_mask)
    update_velocity_histogram(p_rear_vel_hist, telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
        rear_velocity, r_mask)
    update_velocity_band_stats(p_front_vel_stats, front_velocity[f_mask], hst)
    update_velocity_band_stats(p_rear_vel_stats, rear_velocity[r_mask], hst)

def on_doubletap():
    update_travel_histogram(p_front_travel_hist, front_travel, telemetry.Front.DigitizedTravel, front_topouts_mask)
    update_travel_histogram(p_rear_travel_hist, rear_travel, telemetry.Rear.DigitizedTravel, rear_topouts_mask)
    update_fft(p_front_fft, front_travel[front_topouts_mask], tick)
    update_fft(p_rear_fft, rear_travel[rear_topouts_mask], tick)
    update_velocity_histogram(p_front_vel_hist, telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
        front_velocity, front_topouts_mask)
    update_velocity_histogram(p_rear_vel_hist, telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
        rear_velocity, rear_topouts_mask)
    update_velocity_band_stats(p_front_vel_stats, front_velocity[front_topouts_mask], hst)
    update_velocity_band_stats(p_rear_vel_stats, rear_velocity[rear_topouts_mask], hst)

# create graphs
front_color = Spectral11[1]
rear_color = Spectral11[2]
    
p_travel = travel_figure(telemetry, lod, front_color, rear_color)
p_travel.on_event(SelectionGeometry, on_selectiongeometry)
p_travel.on_event(DoubleTap, on_doubletap)

add_airtime_labels(airtimes, tick, p_travel)
add_idling_marks(front_idlings, tick, p_travel)
add_idling_marks(rear_idlings, tick, p_travel)

p_lr = leverage_ratio_figure(np.array(telemetry.Frame.WheelLeverageRatio), Spectral11[5])
p_sw = shock_wheel_figure(telemetry.Frame.CoeffsShockWheel, telemetry.Rear.Calibration.MaxStroke, Spectral11[5])

p_front_travel_hist = travel_histogram_figure(telemetry.Front.DigitizedTravel, front_travel, front_topouts_mask,
    front_color, "Travel histogram (front)")
p_rear_travel_hist = travel_histogram_figure(telemetry.Rear.DigitizedTravel, rear_travel, rear_topouts_mask,
    rear_color, "Travel histogram (rear)")
p_front_vel_hist = velocity_histogram_figure(telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
    front_velocity, front_topouts_mask, hst, "Speed histogram (front)")
p_rear_vel_hist = velocity_histogram_figure(telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
    rear_velocity, rear_topouts_mask, hst, "Speed histogram (rear)")

p_front_vel_stats = velocity_band_stats_figure(front_velocity[front_topouts_mask], hst)
p_rear_vel_stats = velocity_band_stats_figure(rear_velocity[front_topouts_mask], hst)

p_front_fft = fft_figure(front_travel[front_topouts_mask], tick, front_color, "Frequencies (front)")
p_rear_fft = fft_figure(rear_travel[rear_topouts_mask], tick, rear_color, "Frequencies (rear)")

# add graphs to layout
l = layout(
    children=[
        [p_travel, p_lr, p_sw],
        [column(p_front_travel_hist, p_rear_travel_hist), p_front_vel_hist, p_front_vel_stats, p_rear_vel_hist, p_rear_vel_stats],
        [p_front_fft, p_rear_fft],
    ],
    sizing_mode='stretch_width')

curdoc().theme = 'dark_minimal'
curdoc().title = f"Sufni Suspension Telemetry Dashboard ({p})"
curdoc().add_root(l)
