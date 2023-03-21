#!/usr/bin/env python

import argparse
import pytz
import re
import sqlite3

import msgpack
import numpy as np
import requests

from datetime import datetime

from bokeh.events import DoubleTap, MouseMove, SelectionGeometry
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.layouts import Row
from bokeh.models.widgets.buttons import Button
from bokeh.models.widgets.inputs import TextInput, TextAreaInput
from bokeh.models.widgets.markups import Div
from bokeh.palettes import Spectral11

from balance import balance_figures, update_balance
from travel import add_airtime_labels
from fft import fft_figure, update_fft
from leverage import leverage_ratio_figure, shock_wheel_figure
from map import track_data, map_figure_notrack, map_figure
from psst import Telemetry, dataclass_from_dict
from sessions import session_dialog, session_list
from travel import travel_figure, travel_histogram_figure
from travel import update_travel_histogram
from velocity import velocity_figure
from velocity import velocity_histogram_figure, velocity_band_stats_figure
from velocity import update_velocity_band_stats, update_velocity_histogram


parser = argparse.ArgumentParser()
parser.add_argument(
    "-d", "--database",
    required=True,
    help="SQLite database path")
parser.add_argument(
    "-g", "--gosst_api",
    required=False,
    default="http://127.0.0.1:8080",
    help="GoSST HTTP API address:port")
cmd_args = parser.parse_args()

query_args = curdoc().session_context.request.arguments

con = sqlite3.connect(cmd_args.database)
cur = con.cursor()

full_access = False
try:
    token = curdoc().session_context.request.headers['X-Token']
    res = cur.execute('SELECT token FROM tokens')
    full_access = token in [r[0] for r in res.fetchall()]
except BaseException:
    pass

res = cur.execute('''
    SELECT session_id, name, description, timestamp
    FROM sessions
    ORDER BY timestamp DESC''')
sessions = res.fetchall()

if not sessions:
    curdoc().add_root(Div(text="No sessions in the database!"))
    raise Exception("Empty data directory")

try:
    s = int(query_args.get('session')[0].decode('utf-8'))
except BaseException:
    s = sessions[0][0]

res = cur.execute('''
    SELECT name,description,data,track
    FROM sessions
    LEFT JOIN tracks
    ON sessions.track_id = tracks.track_id
    WHERE session_id=?''', (s,))
session_data = res.fetchone()
if not session_data:
    curdoc().add_root(Div(text=f"No session with ID '{s}'"))
    raise Exception("No such session")

session_name = session_data[0]
description = session_data[1]
track_json = session_data[3]
d = msgpack.unpackb(session_data[2])
telemetry = dataclass_from_dict(Telemetry, d)

res = cur.execute('''
    SELECT setups.name,linkages.name,fcal.*,rcal.*
    FROM setups
    INNER JOIN linkages
    ON linkages.linkage_id=setups.linkage_id
    iNNER JOIN calibrations fcal
    ON fcal.calibration_id=setups.front_calibration_id
    INNER JOIN calibrations rcal
    ON rcal.calibration_id=setups.rear_calibration_id
    INNER JOIN sessions
    ON sessions.setup_id=setups.setup_id
    WHERE session_id=?''', (s,))
setup_data = res.fetchone()
if not setup_data:
    curdoc().add_root(Div(text=f"Missing setup data for session '{s}'"))
    raise Exception("Missing setup data")

calibration_table = '''
<table style="width: 100%;">
<tbody>
<tr>
<th>Max. stroke</th>
<td>{} mm</td>
</tr>
<tr>
<th>Max. distance</th>
<td>{} mm</td>
</tr>
<tr>
<th>Arm length</th>
<td>{} mm</td>
</tr>
</tbody>
</table>
'''

setup_figure = Div(
    name='setup',
    sizing_mode='stretch_width',
    height=300,
    stylesheets=['''
        div {
          width: 100%;
          height: 100%;
          padding: 15px;
          background: #15191c;
          font-size: 14px;
          color: #d0d0d0;
        }
        hr {
          border-top:1px dashed #d0d0d0;
          background-color: transparent;
          border-style: none none dashed;
        }
        table, th, td {
          border: 1px dashed #d0d0d0;
          border-collapse: collapse;
          text-align: center;
        }'''],
    text=f'''
        <b>Setup:</b>{setup_data[0]}<br />
        <b>Linkage:</b> {setup_data[1]}<hr />
        <b>Front calibration:</b>{setup_data[3]}<br />
        {calibration_table.format(setup_data[6], setup_data[5], setup_data[4])}
        <br /><b>Rear calibration:</b>{setup_data[9]}<br />
        {calibration_table.format(setup_data[12], setup_data[11], setup_data[10])}
        ''')

# lod - Level of Detail for travel graph (downsample ratio)
try:
    lod = int(query_args.get('lod')[0])
except BaseException:
    lod = 5

# hst - High Speed Threshold for velocity graphs/statistics in mm/s
try:
    hst = int(query_args.get('hst')[0])
except BaseException:
    hst = 350

front_color, rear_color = Spectral11[1], Spectral11[2]
front_record_num, rear_record_num, record_num = 0, 0, 0

tick = 1.0 / telemetry.SampleRate  # time step length in seconds

if telemetry.Front.Present:
    front_record_num = sum([s.Stat.Count for s in
                           telemetry.Front.Strokes.Compressions +
                           telemetry.Front.Strokes.Rebounds])
    p_front_travel_hist = travel_histogram_figure(
        telemetry.Front.Strokes,
        telemetry.Front.TravelBins,
        front_color,
        "Speed histogram (front)")
    p_front_vel_hist = velocity_histogram_figure(
        telemetry.Front.Strokes,
        telemetry.Front.Velocity,
        telemetry.Front.TravelBins,
        telemetry.Front.VelocityBins,
        hst,
        "Speed histogram (front)")
    p_front_vel_stats = velocity_band_stats_figure(
        telemetry.Front.Strokes,
        telemetry.Front.Velocity,
        hst)
    p_front_fft = fft_figure(
        telemetry.Front.Strokes,
        telemetry.Front.Travel,
        tick,
        front_color,
        "Frequencies (front)")

if telemetry.Rear.Present:
    rear_record_num = sum([s.Stat.Count for s in
                           telemetry.Rear.Strokes.Compressions +
                           telemetry.Rear.Strokes.Rebounds])
    p_rear_travel_hist = travel_histogram_figure(
        telemetry.Rear.Strokes,
        telemetry.Rear.TravelBins,
        rear_color,
        "Travel histogram (rear)")
    p_rear_vel_hist = velocity_histogram_figure(
        telemetry.Rear.Strokes,
        telemetry.Rear.Velocity,
        telemetry.Rear.TravelBins,
        telemetry.Rear.VelocityBins,
        hst,
        "Speed histogram (rear)")
    p_rear_vel_stats = velocity_band_stats_figure(
        telemetry.Rear.Strokes,
        telemetry.Rear.Velocity,
        hst)
    p_rear_fft = fft_figure(
        telemetry.Rear.Strokes,
        telemetry.Rear.Travel,
        tick,
        rear_color,
        "Frequencies (rear)")

record_num = front_record_num if front_record_num else rear_record_num
elapsed_time = record_num * tick
start_time = telemetry.Timestamp
end_time = start_time + elapsed_time

'''
Event handlers for travel graph. We update histograms, statistics and FFTs when
a selection is made with the Box Select tool, and when the selection is
cancelled with a double tap.
'''


def on_selectiongeometry(event):
    pass  # XXX
    '''
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
    '''


def on_doubletap():
    pass  # XXX
    '''
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
    '''


p_travel = travel_figure(telemetry, lod, front_color, rear_color)
p_travel.on_event(SelectionGeometry, on_selectiongeometry)
p_travel.on_event(DoubleTap, on_doubletap)
p_velocity = velocity_figure(telemetry, lod, front_color, rear_color)
p_travel.x_range.js_link('start', p_velocity.x_range, 'start')
p_travel.x_range.js_link('end', p_velocity.x_range, 'end')
p_velocity.x_range.js_link('start', p_travel.x_range, 'start')
p_velocity.x_range.js_link('end', p_travel.x_range, 'end')

add_airtime_labels(p_travel, telemetry.Airtimes)


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
        telemetry.Front.Strokes,
        telemetry.Rear.Strokes,
        telemetry.Front.Calibration.MaxStroke,
        telemetry.Linkage.MaxRearTravel,
        front_color,
        rear_color)

'''
Sessions
'''
sessions_list = session_list(sessions, full_access, cmd_args.gosst_api)
session_dialog = session_dialog(cur, full_access, cmd_args.gosst_api)

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
    sizing_mode='stretch_both',
    margin=(0, 0, 0, 0),
    stylesheets=["""
        :host textarea {
            color: #d0d0d0;
            background-color: #20262B;
            font-size: 110%;
            padding: 12px;
            min-height: 180px;
        }"""],
    styles={
        "padding": "5px",
        "padding-top": "0px",
        "padding-bottom": "28px",
        "width": "100%",
        "height": "100%",
        "background-color": "#15191C",
        "color": "#d0d0d0"},
    tags=[description])


def on_savebuttonclick():
    n = name_input.value_input if name_input.value_input else name_input.value
    d = desc_input.value_input if desc_input.value_input else desc_input.value
    r = requests.patch(
        f'{cmd_args.gosst_api}/session/{s}',
        json={"name": n, "desc": d})
    if r.status_code == 204:
        savebutton.disabled = True
        name_input.tags[0] = n
        desc_input.tags[0] = d
        curdoc().title = f"Sufni Suspension Telemetry Dashboard ({n})"
        session_rows = curdoc().select({'name': 'session', 'type': Row})
        for r in session_rows:
            if r.children[0].name == str(s):
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
description_box = column(
    name='description',
    sizing_mode='stretch_both',
    min_height=275,
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

'''
Map
'''
full_track, session_track = track_data(track_json, start_time, end_time)
map = column(
    name='map',
    sizing_mode='stretch_both',
    min_height=340,
    styles={'background-color': '#15191c'})

if session_track is None:
    m = map_figure_notrack(
        s,
        con if full_access else None,
        start_time, end_time,
        map, p_travel)
else:
    m, on_mousemove = map_figure(full_track, session_track)
    p_travel.js_on_event(MouseMove, on_mousemove)

map.children = [m]

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

utc_str = datetime.fromtimestamp(
    start_time, pytz.UTC).strftime('%Y.%m.%d %H:%M')
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
curdoc().add_root(p_lr)
curdoc().add_root(p_sw)
curdoc().add_root(map)
curdoc().add_root(setup_figure)
