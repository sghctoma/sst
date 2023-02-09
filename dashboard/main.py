#!/usr/bin/env python

import re
import pytz
import sqlite3
import sys

import msgpack
import numpy as np
import requests

from datetime import datetime

from bokeh.events import DoubleTap, SelectionGeometry
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.layouts import Row
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets.inputs import TextInput, TextAreaInput
from bokeh.models.widgets.markups import Div
from bokeh.palettes import Spectral11

from balance import balance_figures, update_balance, strokes
from extremes import topouts, combined_topouts
from extremes import intervals_mask, filter_airtimes, filter_idlings
from extremes import add_airtime_labels, add_idling_marks
from fft import fft_figure, update_fft
from leverage import leverage_ratio_figure, shock_wheel_figure
from psst import Telemetry, dataclass_from_dict
from sessions import session_dialog, session_list
from travel import travel_figure, travel_histogram_figure
from travel import update_travel_histogram
from velocity import velocity_figure
from velocity import velocity_histogram_figure, velocity_band_stats_figure
from velocity import update_velocity_band_stats, update_velocity_histogram


DB_FILE = sys.argv[1]

args = curdoc().session_context.request.arguments

con = sqlite3.connect(DB_FILE)
cur = con.cursor()

full_access = False
try:
    token = curdoc().session_context.request.headers['X-Token']
    res = cur.execute('SELECT token FROM tokens')
    full_access = token in [r[0] for r in res.fetchall()]
except BaseException:
    pass

res = cur.execute(
    'SELECT session_id, name, description, timestamp FROM sessions ORDER BY timestamp DESC')
sessions = res.fetchall()

if not sessions:
    curdoc().add_root(Div(text="No sessions in the database!"))
    raise Exception("Empty data directory")

try:
    s = int(args.get('session')[0].decode('utf-8'))
except BaseException:
    s = sessions[0][0]

res = cur.execute('SELECT name,description,data FROM sessions WHERE session_id=?', (s,))
session_data = res.fetchone()
if not session_data:
    curdoc().add_root(Div(text=f"No session with ID '{s}'"))
    raise Exception("No such session")

session_name = session_data[0]
description = session_data[1]
d = msgpack.unpackb(session_data[2])
telemetry = dataclass_from_dict(Telemetry, d)

# lod - Level of Detail for travel graph (downsample ratio)
try:
    lod = int(args.get('lod')[0])
except BaseException:
    lod = 5

# hst - High Speed Threshold for velocity graphs/statistics in mm/s
try:
    hst = int(args.get('hst')[0])
except BaseException:
    hst = 100

tick = 1.0 / telemetry.SampleRate  # time step length in seconds

front_travel, rear_travel = [], []
front_velocity, rear_velocity = [], []
front_topouts, rear_topouts = [], []
front_compressions, rear_compressions = [], []
front_rebounds, rear_rebounds = [], []
front_color, rear_color = Spectral11[1], Spectral11[2]
front_record_num, rear_record_num, record_num = 0, 0, 0

'''
Topouts are intervals where suspension is at zero extension for an extended
period of time. It allows us to filter out e.g. the beginning and the end of
the ride, where the bike is at rest, or intervals where we stop mid-ride.
Filtering these out is important, because they can skew travel and velocity
statistics. They are handled individually for front and rear suspension.
'''
if telemetry.Front.Present:
    front_travel = np.array(telemetry.Front.Travel)
    front_record_num = len(front_travel)
    front_velocity = np.array(telemetry.Front.Velocity)
    front_topouts = topouts(
        front_travel,
        telemetry.Front.Calibration.MaxStroke,
        telemetry.SampleRate)
    front_topouts_mask = intervals_mask(front_topouts, front_record_num)

    front_compressions, front_rebounds = strokes(
        front_velocity, front_travel,
        telemetry.Front.Calibration.MaxStroke * 0.025)
    front_stroke_mask = intervals_mask(
        np.array(front_compressions+front_rebounds),
        front_record_num, False)

    if np.count_nonzero(front_topouts_mask):
        p_front_travel_hist = travel_histogram_figure(
            telemetry.Front.DigitizedTravel,
            front_travel,
            front_topouts_mask,
            front_color,
            "Travel histogram (front)")
        p_front_vel_hist = velocity_histogram_figure(
            telemetry.Front.DigitizedTravel,
            telemetry.Front.DigitizedVelocity,
            front_velocity,
            front_topouts_mask & front_stroke_mask,
            hst,
            "Speed histogram (front)")
        p_front_vel_stats = velocity_band_stats_figure(
            front_velocity[front_topouts_mask & front_stroke_mask], hst)
        p_front_fft = fft_figure(
            front_travel[front_topouts_mask],
            tick,
            front_color,
            "Frequencies (front)")
    else:
        telemetry.Front.Present = False

if telemetry.Rear.Present:
    rear_travel = np.array(telemetry.Rear.Travel)
    rear_record_num = len(rear_travel)
    rear_velocity = np.array(telemetry.Rear.Velocity)
    rear_topouts = topouts(
        rear_travel, telemetry.Linkage.MaxRearTravel, telemetry.SampleRate)
    rear_topouts_mask = intervals_mask(rear_topouts, rear_record_num)

    rear_compressions, rear_rebounds = strokes(
        rear_velocity, rear_travel,
        telemetry.Linkage.MaxRearTravel * 0.025)
    rear_stroke_mask = intervals_mask(
        np.array(rear_compressions+rear_rebounds),
        rear_record_num, False)

    if np.count_nonzero(rear_topouts_mask):
        p_rear_travel_hist = travel_histogram_figure(
            telemetry.Rear.DigitizedTravel,
            rear_travel,
            rear_topouts_mask,
            rear_color,
            "Travel histogram (rear)")
        p_rear_vel_hist = velocity_histogram_figure(
            telemetry.Rear.DigitizedTravel,
            telemetry.Rear.DigitizedVelocity,
            rear_velocity,
            rear_topouts_mask & rear_stroke_mask,
            hst,
            "Speed histogram (rear)")
        p_rear_vel_stats = velocity_band_stats_figure(
            rear_velocity[rear_topouts_mask & rear_stroke_mask], hst)
        p_rear_fft = fft_figure(
            rear_travel[rear_topouts_mask],
            tick,
            rear_color,
            "Frequencies (rear)")
    else:
        telemetry.Rear.Present = False

if not (front_record_num == 0 or rear_record_num ==
        0) and front_record_num != rear_record_num:
    curdoc().add_root(Div(text="SST file is corrupt"))
    raise Exception("Corrupt dataset")

record_num = front_record_num if front_record_num else rear_record_num

'''
Event handlers for travel graph. We update histograms, statistics and FFTs when
a selection is made with the Box Select tool, and when the selection is
cancelled with a double tap.
'''


def on_selectiongeometry(event):
    start = int(event.geometry['x0'] * telemetry.SampleRate)
    end = int(event.geometry['x1'] * telemetry.SampleRate)
    mask = np.full(record_num, False)
    mask[start:end] = True

    if telemetry.Front.Present:
        f_mask = front_topouts_mask & mask
        if np.count_nonzero(f_mask):
            update_travel_histogram(
                p_front_travel_hist,
                front_travel,
                telemetry.Front.Calibration.MaxStroke,
                telemetry.Front.DigitizedTravel,
                f_mask)
            update_fft(p_front_fft, front_travel[f_mask], tick)
            update_velocity_histogram(
                p_front_vel_hist,
                telemetry.Front.DigitizedTravel,
                telemetry.Front.DigitizedVelocity,
                front_velocity,
                f_mask & front_stroke_mask)
            update_velocity_band_stats(
                p_front_vel_stats,
                front_velocity[f_mask & front_stroke_mask],
                hst)

    if telemetry.Rear.Present:
        r_mask = rear_topouts_mask & mask
        if np.count_nonzero(r_mask):
            update_travel_histogram(
                p_rear_travel_hist,
                rear_travel,
                telemetry.Linkage.MaxRearTravel,
                telemetry.Rear.DigitizedTravel,
                r_mask)
            update_fft(p_rear_fft, rear_travel[r_mask], tick)
            update_velocity_histogram(
                p_rear_vel_hist,
                telemetry.Rear.DigitizedTravel,
                telemetry.Rear.DigitizedVelocity,
                rear_velocity,
                r_mask & rear_stroke_mask)
            update_velocity_band_stats(
                p_rear_vel_stats,
                rear_velocity[r_mask & rear_stroke_mask],
                hst)

    if telemetry.Front.Present and telemetry.Rear.Present:
        update_balance(
            p_balance_compression,
            p_balance_rebound,
            front_travel[mask],
            telemetry.Front.Calibration.MaxStroke,
            front_velocity[mask],
            rear_travel[mask],
            telemetry.Linkage.MaxRearTravel,
            rear_velocity[mask])


def on_doubletap():
    if telemetry.Front.Present:
        update_travel_histogram(
            p_front_travel_hist,
            front_travel,
            telemetry.Front.Calibration.MaxStroke,
            telemetry.Front.DigitizedTravel,
            front_topouts_mask)
        update_fft(p_front_fft, front_travel[front_topouts_mask], tick)
        update_velocity_histogram(
            p_front_vel_hist,
            telemetry.Front.DigitizedTravel,
            telemetry.Front.DigitizedVelocity,
            front_velocity,
            front_topouts_mask & front_stroke_mask)
        update_velocity_band_stats(
            p_front_vel_stats,
            front_velocity[front_topouts_mask & front_stroke_mask],
            hst)

    if telemetry.Rear.Present:
        update_travel_histogram(
            p_rear_travel_hist,
            rear_travel,
            telemetry.Linkage.MaxRearTravel,
            telemetry.Rear.DigitizedTravel,
            rear_topouts_mask)
        update_fft(p_rear_fft, rear_travel[rear_topouts_mask], tick)
        update_velocity_histogram(
            p_rear_vel_hist,
            telemetry.Rear.DigitizedTravel,
            telemetry.Rear.DigitizedVelocity,
            rear_velocity,
            rear_topouts_mask & rear_stroke_mask)
        update_velocity_band_stats(
            p_rear_vel_stats,
            rear_velocity[rear_topouts_mask & rear_stroke_mask],
            hst)

    if telemetry.Front.Present and telemetry.Rear.Present:
        update_balance(
            p_balance_compression,
            p_balance_rebound,
            front_travel,
            telemetry.Front.Calibration.MaxStroke,
            front_velocity,
            rear_travel,
            telemetry.Linkage.MaxRearTravel,
            rear_velocity)


p_travel = travel_figure(telemetry, lod, front_color, rear_color)
p_travel.on_event(SelectionGeometry, on_selectiongeometry)
p_travel.on_event(DoubleTap, on_doubletap)
p_velocity = velocity_figure(telemetry, lod, front_color, rear_color)
p_travel.x_range.js_link('start', p_velocity.x_range, 'start')
p_travel.x_range.js_link('end', p_velocity.x_range, 'end')
p_velocity.x_range.js_link('start', p_travel.x_range, 'start')
p_velocity.x_range.js_link('end', p_travel.x_range, 'end')

'''
We use both suspensions to find airtimes. Basically, everything is considered
airtime if both suspensions are close to zero travel, and suspension velocity
at the end of the interval reaches a threshold. A few remarks:
 - Originally, I used a velocity threshold at the beginning too of a candidate
   interval, but there were a lot of alse negatives usually with drops.
 - We use the mean of front and rear travel to determine closeness to zero.
   This is based on the empirical observation that sometimes one of the
   suspensions (usually my fork) oscillates outside the set threshold during
   airtime (usually during drops). I expect this to become a problem if anybody
   else starts using this program, but could not come up with better heuristics
   so far.
'''
comb_topouts = combined_topouts(
    front_travel if telemetry.Front.Present else np.full(
        record_num,
        0),
    telemetry.Front.Calibration.MaxStroke,
    rear_travel if telemetry.Rear.Present else np.full(
        record_num,
        0),
    telemetry.Linkage.MaxRearTravel,
    telemetry.SampleRate)
airtimes = filter_airtimes(
    comb_topouts, front_velocity if telemetry.Front.Present else np.full(
        record_num, 0), rear_velocity if telemetry.Rear.Present else np.full(
        record_num, 0), telemetry.SampleRate)
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
p_lr = leverage_ratio_figure(
    np.array(telemetry.Linkage.LeverageRatio), Spectral11[5])
p_sw = shock_wheel_figure(telemetry.Linkage.ShockWheelCoeffs,
                          telemetry.Rear.Calibration.MaxStroke, Spectral11[5])

'''
Compression and rebound velocity balance
'''
if telemetry.Front.Present and telemetry.Rear.Present:
    p_balance_compression, p_balance_rebound = balance_figures(
        front_travel,
        telemetry.Front.Calibration.MaxStroke,
        front_velocity,
        front_color,
        rear_travel,
        telemetry.Linkage.MaxRearTravel,
        rear_velocity,
        rear_color)

'''
Sessions
'''
sessions_list = session_list(sessions, full_access)
session_dialog = session_dialog(cur, full_access)

'''
Description
'''
savebutton = Button(
    label="save",
    disabled=True,
    sizing_mode='fixed',
    height=25,
    width=45,
    button_type='success',
    styles={
        "position": "unset",
        "margin-left": "auto",
        "margin-right": "5px"})

name_input = TextInput(
    value=session_name,
    sizing_mode='stretch_width',
    margin=(0, 0, 0, 0),
    styles={
        "padding": "5px",
        "width": "100%",
        "background-color": "#15191C",
        "color": "#d0d0d0"},
    stylesheets=["""
        :host input {
            color: #d0d0d0;
            background-color: #20262B;
            font-size: 110%;
        }"""],
    tags=[session_name])

desc_input = TextAreaInput(
    value=description,
    rows=5,
    sizing_mode='stretch_both',
    margin=(0, 0, 0, 0),
    stylesheets=["""
        :host textarea {
            color: #d0d0d0;
            background-color: #20262B;
            font-size: 110%;
            padding: 12px;
        }"""],
    styles={
        "padding": "5px",
        "padding-top": "0px",
        "padding-bottom": "53px",
        "width": "100%",
        "height": "100%",
        "background-color": "#15191C",
        "color": "#d0d0d0"},
    tags=[description])


def on_savebuttonclick():
    n = name_input.value_input if name_input.value_input else name_input.value
    d = desc_input.value_input if desc_input.value_input else desc_input.value
    r = requests.patch(
        f'http://127.0.0.1:8080/session/{s}',
        json={"name": n, "desc": d})
    if r.status_code == 204:
        savebutton.disabled = True
        name_input.tags[0] = n
        desc_input.tags[0] = d
        curdoc().title = f"Sufni Suspension Telemetry Dashboard ({n})"
        session_rows = curdoc().select({'name': 'session', 'type': Row})
        for r in session_rows:
            if r.children[0].id == s:
                r.children[0].text = f"""
                    &nbsp;&nbsp;
                    <a href='dashboard?session={s}'>{n}</a>
                    <span class='tooltiptext'>{d}</span>
                    """
    else:
        savebutton.disabled = False


desc_input.js_on_change('value_input', CustomJS(
    args=dict(btn=savebutton, n=name_input), code='''
    let name_changed = (n.value != n.tags[0]);
    let name_empty = (n.value == "");
    let desc_changed = (this.value_input != this.tags[0]);
    btn.disabled = name_empty || !(name_changed || desc_changed);
    '''))
name_input.js_on_change('value_input', CustomJS(
    args=dict(btn=savebutton, d=desc_input), code='''
    let name_changed = (this.value_input != this.tags[0]);
    let name_empty = (this.value_input == "");
    let desc_changed = (d.value != d.tags[0]);
    btn.disabled = name_empty || !(name_changed || desc_changed);
    '''))
name_input.js_on_change('tags', CustomJS(args=dict(), code='''
    document.getElementById("sname").innerHTML = this.value;
    '''))
savebutton.on_click(on_savebuttonclick)

children = [Div(text="<h3>Notes</h3>",
                sizing_mode='stretch_width',
                height=25,
                stylesheets=[":host h3 {margin-block-start: 0px;}"])]
if full_access:
    children.append(savebutton)
text = column(name='description_x',
              sizing_mode='stretch_width',
              height=300,
              children=[row(sizing_mode='stretch_width',
                            height=30,
                            margin=(0, 0, 0, 0),
                            styles={
                                "width": "100%",
                                "background-color": "#15191C",
                                "color": "#d0d0d0"},
                            children=children),
                        name_input,
                        desc_input])
description_box = row(
    name='description',
    sizing_mode='stretch_width',
    height=300,
    children=[p_lr, text])

'''
Disable tools for mobile browsers to allow scrolling
'''


def disable_tools(p):
    p.toolbar.active_drag = None
    p.toolbar.active_scroll = None
    p.toolbar.active_inspect = None


ua = ''
try:
    ua = curdoc().session_context.request.headers['User-Agent']
except BaseException:
    pass
if re.search(
    'Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini',
        ua) is not None:
    disable_tools(p_travel)
    disable_tools(p_lr)
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
suspension_count = 0
if telemetry.Front.Present:
    suspension_count += 1
if telemetry.Rear.Present:
    suspension_count += 1

utc = datetime.fromtimestamp(telemetry.Timestamp, pytz.timezone('UTC'))
utc_str = utc.strftime('%Y.%m.%d %H:%M')
curdoc().theme = 'dark_minimal'
curdoc().title = f"Sufni Suspension Telemetry Dashboard ({session_name})"
curdoc().template_variables["suspension_count"] = suspension_count
curdoc().template_variables["name"] = session_name
curdoc().template_variables["date"] = utc_str
curdoc().add_root(p_travel)
curdoc().add_root(p_velocity)
if telemetry.Front.Present:
    prefix = 'front_' if suspension_count == 2 else ''
    p_front_travel_hist.name = f'{prefix}travel_hist'
    p_front_fft.name = f'{prefix}fft'
    p_front_velocity = row(
        name=f'{prefix}velocity_hist',
        sizing_mode='stretch_width',
        children=[
            p_front_vel_hist,
            p_front_vel_stats])
    curdoc().add_root(p_front_travel_hist)
    curdoc().add_root(p_front_fft)
    curdoc().add_root(p_front_velocity)
if telemetry.Rear.Present:
    prefix = 'rear_' if suspension_count == 2 else ''
    p_rear_travel_hist.name = f'{prefix}travel_hist'
    p_rear_fft.name = f'{prefix}fft'
    p_rear_velocity = row(
        name=f'{prefix}velocity_hist',
        sizing_mode='stretch_width',
        children=[
            p_rear_vel_hist,
            p_rear_vel_stats])
    curdoc().add_root(p_rear_travel_hist)
    curdoc().add_root(p_rear_fft)
    curdoc().add_root(p_rear_velocity)
if suspension_count == 2:
    curdoc().add_root(p_balance_compression)
    curdoc().add_root(p_balance_rebound)
curdoc().add_root(sessions_list)
curdoc().add_root(session_dialog)
curdoc().add_root(description_box)
