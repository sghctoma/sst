import math
import numpy as np
import xyzservices.providers as xyz

from gpx_converter import Converter
from bokeh.models import ColumnDataSource
from bokeh.models.widgets.markups import Div
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


def map_figure(ds_track, ds_session):
    if ds_track is None:
        return Div(
            name='map',
            sizing_mode='stretch_width',
            height=677,
            text="no track data for session")
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
    return p
