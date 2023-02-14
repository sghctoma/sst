import math
import numpy as np
import xyzservices.providers as xyz

from gpx_converter import Converter
from bokeh.models import Circle, ColumnDataSource
from bokeh.models.callbacks import CustomJS
from bokeh.layouts import layout
from bokeh.models.widgets.inputs import FileInput
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from scipy.interpolate import pchip_interpolate


def geographic_to_mercator(x_lon, y_lat):
    if abs(x_lon) > 180 or abs(y_lat) >= 90:
        return None

    num = x_lon * 0.017453292519943295
    x_m = 6378137.0 * num
    a = y_lat * 0.017453292519943295
    y_m = 3189068.5 * math.log((1.0 + math.sin(a)) / (1.0 - math.sin(a)))
    return x_m, y_m


def track_data(filename, start_time, end_time):
    track = Converter(input_file=filename).gpx_to_dictionary(
        latitude_key='lat',
        longitude_key='lon')
    for i in range(len(track['time'])):
        track['lon'][i], track['lat'][i] = geographic_to_mercator(
            track['lon'][i], track['lat'][i])
    t = np.array(track.pop('time', None))  # we don't need time in the ds
    ds_track = ColumnDataSource(data=track)

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

    session_lon = np.array(track['lon'][start_idx:end_idx])
    session_lat = np.array(track['lat'][start_idx:end_idx])
    session_time = np.array(t[start_idx:end_idx]) - start_time
    session_time = [t.total_seconds() * 1000 for t in session_time]
    session_time[0] = 0

    tms = (end_time - start_time).total_seconds() * 1000
    x = np.arange(0, tms + 100, 100)
    yi = np.array([session_lon, session_lat])
    y = pchip_interpolate(session_time, yi, x, axis=1)

    session_data = dict(lon=y[0, :], lat=y[1, :])
    ds_session = ColumnDataSource(data=session_data)

    return ds_track, ds_session


def no_gpx_figure(full_access):
    file_input = FileInput(
        name='input_gpx',
        accept='.gpx',
        title="Upload GPX track" if full_access else "No GPX track for session",
        disabled=not full_access,
        stylesheets=['''
            input[type="file"] {
              opacity: 0 !important;
              cursor: pointer;
              position: absolute;
              top: 0;
              left: 0;
            }
            label {
              border: 1px dashed #ccc;
              display: inline-block;
              padding: 6px 12px;
              font-size: 14px;
              color: #d0d0d0;
              cursor: pointer;
            }
            :host(.gpxbutton) {
              margin: auto;
            }'''],
        css_classes=['gpxbutton'])

    def upload_gpx_data(attr, old, new):
        print(file_input.value)

    if full_access:
        file_input.on_change('value', upload_gpx_data)

    return layout(
        name='map',
        sizing_mode='stretch_width',
        height=677,
        styles={'background-color': '#15191c'},
        children=[file_input])


def map_figure(gpx_file, start_time, end_time, full_access):
    ds_track, ds_session = track_data(gpx_file, start_time, end_time)
    if ds_track is None:
        return no_gpx_figure(full_access), None

    start_lon = ds_session.data['lon'][0]
    start_lat = ds_session.data['lat'][0]

    p = figure(
        name='map',
        x_axis_type=None,
        y_axis_type=None,
        x_range=[start_lon - 600, start_lon + 600],
        y_range=[start_lat - 600, start_lat + 600],
        sizing_mode='stretch_width',
        height=677,
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
