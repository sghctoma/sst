#!/usr/bin/env python3

import argparse
import json
import sqlite3

import msgpack
import numpy as np

from bokeh.events import MouseMove
from bokeh.embed import components, json_item
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models.widgets.markups import Div
from bokeh.palettes import Spectral11
from bokeh.themes import built_in_themes, DARK_MINIMAL

from balance import balance_figure
from fft import fft_figure
from leverage import leverage_ratio_figure, shock_wheel_figure
from map import track_data, map_figure_notrack, map_figure
from psst import Telemetry, dataclass_from_dict
from travel import travel_figure, travel_histogram_figure
from velocity import velocity_figure
from velocity import velocity_histogram_figure, velocity_band_stats_figure


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
parser.add_argument(
    "-s", "--session",
    type=int,
    required=True,
    help="Session ID")
parser.add_argument(
    "-l", "--lod",
    required=False,
    type=int,
    default=5,
    help="Level of detail for graphs")
parser.add_argument(
    "-t", "--hst",
    required=False,
    type=int,
    default=350,
    help="High speed threshold")
cmd_args = parser.parse_args()

lod = cmd_args.lod
hst = cmd_args.hst
s = cmd_args.session

con = sqlite3.connect(cmd_args.database)
cur = con.cursor()

full_access = False  # XXX

res = cur.execute('''
    SELECT name,description,data,track
    FROM sessions
    LEFT JOIN tracks
    ON sessions.track_id = tracks.track_id
    WHERE session_id=?''', (s,))
session_data = res.fetchone()
if not session_data:
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

p_setup = Div(
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

front_color, rear_color = Spectral11[1], Spectral11[2]
front_record_num, rear_record_num, record_num = 0, 0, 0

tick = 1.0 / telemetry.SampleRate  # time step length in seconds

if telemetry.Front.Present:
    front_record_num = len(telemetry.Front.Travel)
    p_front_travel_hist = travel_histogram_figure(
        telemetry.Front.Strokes,
        telemetry.Front.TravelBins,
        front_color,
        "Travel histogram (front)")
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
    rear_record_num = len(telemetry.Rear.Travel)
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

p_travel = travel_figure(telemetry, lod, front_color, rear_color)
p_velocity = velocity_figure(telemetry, lod, front_color, rear_color)
p_travel.x_range.js_link('start', p_velocity.x_range, 'start')
p_travel.x_range.js_link('end', p_velocity.x_range, 'end')
p_velocity.x_range.js_link('start', p_travel.x_range, 'start')
p_velocity.x_range.js_link('end', p_travel.x_range, 'end')

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
    p_balance_compression = balance_figure(
        telemetry.Front.Strokes.Compressions,
        telemetry.Rear.Strokes.Compressions,
        telemetry.Front.Calibration.MaxStroke,
        telemetry.Linkage.MaxRearTravel,
        False,
        front_color,
        rear_color,
        'balance_compression',
        "Compression velocity balance")
    p_balance_rebound = balance_figure(
        telemetry.Front.Strokes.Rebounds,
        telemetry.Rear.Strokes.Rebounds,
        telemetry.Front.Calibration.MaxStroke,
        telemetry.Linkage.MaxRearTravel,
        True,
        front_color,
        rear_color,
        'balance_rebound',
        "Rebound velocity balance")


'''
Map
'''
full_track, session_track = track_data(track_json, start_time, end_time)
p_map = column(
    name='map',
    sizing_mode='stretch_both',
    min_height=340,
    styles={'background-color': '#15191c'})

if session_track is None:
    m = map_figure_notrack(
        s,
        con if full_access else None,
        start_time, end_time,
        p_map, p_travel)
else:
    m, on_mousemove = map_figure(full_track, session_track)
    p_travel.js_on_event(MouseMove, on_mousemove)

p_map.children = [m]

'''
Construct the layout.
'''
suspension_count = 0
if telemetry.Front.Present:
    suspension_count += 1
if telemetry.Rear.Present:
    suspension_count += 1

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

dark_minimal_theme = built_in_themes[DARK_MINIMAL]

curdoc().add_root(p_travel)
curdoc().add_root(p_velocity)
curdoc().add_root(p_map)
curdoc().add_root(p_lr)
curdoc().add_root(p_sw)
curdoc().add_root(p_setup)
script, divs = components(curdoc().roots, theme=dark_minimal_theme)

cur.execute('''
    INSERT INTO bokeh_cache (
        session_id,
        script,
        div_travel,
        div_velocity,
        div_map,
        div_lr,
        div_sw,
        div_setup,
        json_f_fft,
        json_r_fft,
        json_f_thist,
        json_r_thist,
        json_f_vhist,
        json_r_vhist,
        json_cbalance,
        json_rbalance)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        s,
        script,
        divs[0], divs[1], divs[2], divs[3], divs[4], divs[5],
        json.dumps(json_item(p_front_fft, theme=dark_minimal_theme)),
        json.dumps(json_item(p_rear_fft, theme=dark_minimal_theme)),
        json.dumps(json_item(p_front_travel_hist, theme=dark_minimal_theme)),
        json.dumps(json_item(p_rear_travel_hist, theme=dark_minimal_theme)),
        json.dumps(json_item(p_front_velocity, theme=dark_minimal_theme)),
        json.dumps(json_item(p_rear_velocity, theme=dark_minimal_theme)),
        json.dumps(json_item(p_balance_compression, theme=dark_minimal_theme)),
        json.dumps(json_item(p_balance_rebound, theme=dark_minimal_theme)),
    ))
con.commit()
