import base64
import math
import numpy as np
import os
import xyzservices.providers as xyz

from uuid import uuid4

from gpx_converter import Converter
from bokeh.models import Circle, ColumnDataSource
from bokeh.models.callbacks import CustomJS
from bokeh.layouts import layout
from bokeh.models.widgets.inputs import FileInput
from bokeh.models.widgets.markups import Div
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from scipy.interpolate import pchip_interpolate


GPX_STORE = '../database/gpx'


def _geographic_to_mercator(x_lon, y_lat):
    if abs(x_lon) > 180 or abs(y_lat) >= 90:
        return None

    num = x_lon * 0.017453292519943295
    x_m = 6378137.0 * num
    a = y_lat * 0.017453292519943295
    y_m = 3189068.5 * math.log((1.0 + math.sin(a)) / (1.0 - math.sin(a)))
    return x_m, y_m


def _track_timeframe(gpx_file):
    track = None
    try:
        track = Converter(input_file=gpx_file).gpx_to_dictionary(
            altitude_key=None,
            latitude_key=None,
            longitude_key=None)
    except Exception as e:
        print(e)
        return None, None

    return track['time'][0], track['time'][-1]


def track_data(gpx_file, start_time, end_time):
    if not gpx_file:
        return None, None

    gpx_path = os.path.join(GPX_STORE, gpx_file)
    full_track = None
    try:
        full_track = Converter(input_file=gpx_path).gpx_to_dictionary(
            latitude_key='lat',
            longitude_key='lon')
        full_track.pop('altitude')
    except Exception:
        return None, None

    for i in range(len(full_track['time'])):
        full_track['lon'][i], full_track['lat'][i] = _geographic_to_mercator(
            full_track['lon'][i], full_track['lat'][i])
    t = np.array(full_track.pop('time', None))  # we don't need time in the ds

    session_indices = np.where(np.logical_and(t >= start_time, t <= end_time))
    if len(session_indices[0]) == 0:
        return None, None

    start_idx = session_indices[0][0]
    end_idx = session_indices[0][-1] + 1  # +1, so that the last is included
    # Use previous location if first GPS data point is after start_time. This
    # makes location estimates more realistic in case GPS tracking turns on
    # after we started data acquisition (e.g. Garmin auto-start needs 10 km/h)
    # to start tracking.
    if t[start_idx] > start_time:
        start_idx -= 1

    session_lon = np.array(full_track['lon'][start_idx:end_idx])
    session_lat = np.array(full_track['lat'][start_idx:end_idx])
    session_time = np.array(t[start_idx:end_idx]) - start_time
    session_time = [t.total_seconds() * 1000 for t in session_time]
    session_time[0] = 0

    tms = (end_time - start_time).total_seconds() * 1000
    x = np.arange(0, tms + 100, 100)
    yi = np.array([session_lon, session_lat])
    y = pchip_interpolate(session_time, yi, x, axis=1)

    session_track = dict(lon=y[0, :], lat=y[1, :])

    return full_track, session_track


def _notrack_label():
    label = Div(
        text="No GPX track for session",
        stylesheets=['''
            :host(.notracklabel)>.bk-clearfix {
              border: 1px dashed #ccc;
              padding: 6px 12px;
              font-size: 14px;
              color: #a0a0a0;
              height: 34px;
              justify-self: center;
              align-self: center;
              grid-area: 1/1;
            }
            :host(.notracklabel) {
              display: grid;
            }'''],
        css_classes=['notracklabel'])
    return label


def _upload_button(con, id):
    file_input = FileInput(
        name='input_gpx',
        accept='.gpx',
        title="Upload GPX track",
        stylesheets=['''
            input[type="file"] {
              opacity: 0 !important;
              cursor: pointer;
              width: 140px;
              height: 34px;
              justify-self: center;
              align-self: center;
              grid-area: 1/1;
            }
            label {
              border: 1px dashed #ccc;
              padding: 6px 12px;
              font-size: 14px;
              color: #d0d0d0;
              cursor: pointer;
              width: 140px;
              height: 34px;
              justify-self: center;
              align-self: center;
              grid-area: 1/1;
            }
            :host(.gpxbutton)>.bk-input-group {
              display: grid;
            }'''],
        css_classes=['gpxbutton'])

    def upload_gpx_data(attr, old, new):
        gpx_data = base64.b64decode(file_input.value)
        gpx_file = f'{uuid4()}.gpx'
        gpx_path = os.path.join(GPX_STORE, gpx_file)
        with open(gpx_path, 'wb') as f:
            f.write(gpx_data)
        ts, tf = _track_timeframe(gpx_path)
        cur = con.cursor()
        cur.execute('''
            UPDATE sessions
            SET gpx_file=?
            WHERE session_id
            IN (
                SELECT s2.session_id
                FROM sessions s1
                INNER JOIN sessions s2
                ON s1.setup_id=s2.setup_id
                WHERE s1.session_id=?
                AND s2.timestamp>=?
                AND s2.timestamp<=?
            )''', (gpx_file, id, ts.timestamp(), tf.timestamp()))
        con.commit()
        cur.close()

    file_input.on_change('value', upload_gpx_data)
    return file_input


def map_figure_notrack(session_id, con, full_access):
    if full_access:
        content = _upload_button(con, session_id)
    else:
        content = _notrack_label()

    return layout(
        name='map',
        sizing_mode='stretch_both',
        min_height=340,
        styles={'background-color': '#15191c'},
        children=[content])


def map_figure(full_track, session_track):
    ds_track = ColumnDataSource(data=full_track)
    ds_session = ColumnDataSource(data=session_track)

    start_lon = ds_session.data['lon'][0]
    start_lat = ds_session.data['lat'][0]

    p = figure(
        name='map',
        x_axis_type=None,
        y_axis_type=None,
        x_range=[start_lon - 600, start_lon + 600],
        y_range=[start_lat - 600, start_lat + 600],
        sizing_mode='stretch_both',
        min_height=340,
        match_aspect=True,
        tools='pan,wheel_zoom,reset',
        active_drag='pan',
        active_scroll='wheel_zoom',
        output_backend='webgl')
    tile_provider = xyz.Jawg.Dark(
        accessToken='lK4rYCmlPZb5Fj4GjObrgGYo0IQnEz00hWXR7lpmRUHQ2a9R6jwr8aEpaSJxh5tn',
        variant='aa40616c-c117-442e-ae6f-901ffa0e14a4'
    )
    p.add_tile(tile_provider)
    p.line(x='lon', y='lat', source=ds_track,
           color=Spectral11[3], alpha=0.5, width=2)
    p.circle(x=ds_track.data['lon'][0], y=ds_track.data['lat'][0],
             color='#229954', alpha=0.8, size=10)
    p.circle(x=ds_track.data['lon'][-1], y=ds_track.data['lat'][-1],
             color='#E74C3C', alpha=0.8, size=10)
    p.line(x='lon', y='lat', source=ds_session,
           color=Spectral11[10], alpha=0.8, width=5)

    pos_marker = Circle(
        x=ds_session.data['lon'][0],
        y=ds_session.data['lat'][0],
        size=13,
        line_color='black',
        fill_color='gray')
    p.add_glyph(pos_marker)

    on_mousemove = CustomJS(
        args=dict(dss=ds_session, pos=pos_marker),
        code='''
            let idx = Math.floor(cb_obj.x * 10);
            if (idx < 0) {
                idx = 0;
            } else if (idx >= dss.data['lon'].length) {
                idx = dss.data['lon'].length - 1;
            }
            let lon = dss.data['lon'][idx];
            let lat = dss.data['lat'][idx];
            pos.x = lon;
            pos.y = lat;''')

    return p, on_mousemove
